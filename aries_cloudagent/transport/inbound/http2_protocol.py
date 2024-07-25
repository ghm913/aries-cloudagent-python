import asyncio
import logging
import time
from email.utils import formatdate
from typing import Callable, Dict, Optional

import h2.config
import h2.connection
import h2.events

SERVER_NAME = "http2-client/0.1"

class HttpRequestHandler:
    def __init__(
            self,
            *,
            connection: h2.connection.H2Connection,
            stream_id: int,
            transmit: Callable[[], None],
            scope: Dict,
            stream_ended: bool
    ) -> None:
        self.connection = connection
        self.stream_id = stream_id
        self.transmit = transmit
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.scope = scope

        if stream_ended:
            self.queue.put_nowait({"type": "http.request"})

    def http_event_received(self, event: h2.events.Event) -> None:
        if isinstance(event, h2.events.DataReceived):
            self.queue.put_nowait(
                {
                    "type": "http.request",
                    "body": event.data,
                    "more_body": not event.stream_ended,
                }
            )
        elif isinstance(event, h2.events.RequestReceived) and event.stream_ended:
            self.queue.put_nowait(
                {"type": "http.request", "body": b"", "more_body": False}
            )

    async def run_asgi(self, app: Callable) -> None:
        await app(self.scope, self.receive, self.send)

    async def receive(self) -> Dict:
        return await self.queue.get()

    async def send(self, message: Dict) -> None:
        if message["type"] == "http.response.start":
            headers = [(b":status", str(message["status"]).encode())]
            for k, v in message["headers"]:
                headers.append((k.encode(), v.encode()))
            headers.append((b"server", SERVER_NAME.encode()))
            headers.append((b"date", formatdate(time.time(), usegmt=True).encode()))

            self.connection.send_headers(stream_id=self.stream_id, headers=headers)
        elif message["type"] == "http.response.body":
            self.connection.send_data(
                stream_id=self.stream_id,
                data=message.get("body", b""),
                end_stream=not message.get("more_body", False),
            )
        self.transmit()

class Http2ServerProtocol(asyncio.Protocol):
    def __init__(self, app: Callable, *args, **kwargs) -> None:
        self.app = app
        self.connection = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
        self._handlers: Dict[int, HttpRequestHandler] = {}
        self._loop = asyncio.get_event_loop()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport
        self.connection.initiate_connection()
        self.transmit()

    def data_received(self, data: bytes) -> None:
        events = self.connection.receive_data(data)
        for event in events:
            self.http_event_received(event)
        self.transmit()

    def http_event_received(self, event: h2.events.Event) -> None:
        if isinstance(event, h2.events.RequestReceived):
            headers = []
            method = ""
            raw_path = b""
            for name, value in event.headers:
                if name == ":method":
                    method = value.decode()
                elif name == ":path":
                    raw_path = value
                elif not name.startswith(":"):
                    headers.append((name.encode(), value.encode()))

            path, query_string = (raw_path.split(b"?", 1) + [b""])[:2]

            scope = {
                "type": "http",
                "http_version": "2",
                "asgi": {"version": "3.0"},
                "method": method,
                "scheme": "https",
                "path": path.decode("ascii"),
                "raw_path": raw_path,
                "query_string": query_string,
                "headers": headers,
                "client": self._transport.get_extra_info("peername"),
                "server": self._transport.get_extra_info("sockname"),
            }

            handler = HttpRequestHandler(
                connection=self.connection,
                stream_id=event.stream_id,
                transmit=lambda: self.transmit(),
                scope=scope,
                stream_ended=event.stream_ended
            )
            self._handlers[event.stream_id] = handler
            asyncio.ensure_future(handler.run_asgi(self.app))
            handler.http_event_received(event)
        elif isinstance(event, h2.events.DataReceived):
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)
        elif isinstance(event, h2.events.StreamEnded):
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        pass

    def eof_received(self) -> None:
        pass

    def transmit(self) -> None:
        if self._transport is not None:
            self._transport.write(self.connection.data_to_send())
