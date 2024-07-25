import asyncio
import logging
from collections import deque, OrderedDict
from typing import Deque, Dict, Optional
from urllib.parse import urlparse

import h2.config
import h2.connection
import h2.events

logger = logging.getLogger("client")

USER_AGENT = "http2-client/0.1"

class Http2Client(asyncio.Protocol):
    def __init__(self) -> None:
        self._conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True))
        self.pushes: Dict[int, Deque[h2.events.Event]] = {}
        self._request_events: Dict[int, Deque[h2.events.Event]] = {}
        self._request_waiter: Dict[int, asyncio.Future[Deque[h2.events.Event]]] = {}
        self.http_response_headers = OrderedDict()
        self.http_response_data = bytearray()

    def http_event_received(self, event: h2.events.Event) -> None:
        if isinstance(event, (h2.events.ResponseReceived, h2.events.DataReceived)):
            stream_id = event.stream_id
            if stream_id in self._request_events:
                self._request_events[event.stream_id].append(event)
                if event.stream_ended:
                    request_waiter = self._request_waiter.pop(stream_id)
                    request_waiter.set_result(self._request_events.pop(stream_id))

        if isinstance(event, h2.events.DataReceived):
            self.http_response_data.extend(event.data)

        if isinstance(event, h2.events.ResponseReceived):
            for k, v in event.headers:
                self.http_response_headers[k.decode()] = v.decode()

    def data_received(self, data: bytes) -> None:
        events = self._conn.receive_data(data)
        for event in events:
            self.http_event_received(event)
        self.transport.write(self._conn.data_to_send())

    async def send_http_request(self, url: str, method: str = "GET", data: Optional[str] = None, headers: Optional[Dict] = None):
        if headers is None:
            headers = {}

        parsed = urlparse(url)
        authority = parsed.netloc
        path = parsed.path or "/"

        stream_id = self._conn.get_next_available_stream_id()
        self._conn.send_headers(
            stream_id=stream_id,
            headers=[
                (':method', method),
                (':scheme', 'https'),
                (':authority', authority),
                (':path', path),
                ('user-agent', USER_AGENT),
            ] + [(k, v) for (k, v) in headers.items()],
            end_stream=not data,
        )
        if data:
            self._conn.send_data(
                stream_id=stream_id, data=data.encode(), end_stream=True
            )

        waiter = asyncio.get_event_loop().create_future()
        self._request_events[stream_id] = deque()
        self._request_waiter[stream_id] = waiter
        self.transport.write(self._conn.data_to_send())

        await asyncio.shield(waiter)

        return self.http_response_data, self.http_response_headers

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport
        self._conn.initiate_connection()
        self.transport.write(self._conn.data_to_send())

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.transport = None
