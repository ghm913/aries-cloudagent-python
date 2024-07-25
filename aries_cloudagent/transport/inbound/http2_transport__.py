import asyncio
import logging
from typing import Union, Optional
from aiohttp import web

from aries_cloudagent.transport.inbound.http2_protocol import Http2ServerProtocol
from aries_cloudagent.transport.inbound.base import BaseInboundTransport, InboundTransportSetupError
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.messaging.error import MessageParseError
from aries_cloudagent.transport.error import WireFormatParseError

from ..wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE

LOGGER = logging.getLogger(__name__)

class Http2Transport(BaseInboundTransport):
    """Http2 Transport class."""

    def __init__(self, host: str, port: int, create_session, **kwargs) -> None:
        """Initialize an inbound HTTP/2 transport instance.

        Args:
            host: Host to listen on
            port: Port to listen on
            create_session: Method to create a new inbound session
        """
        super().__init__("https", create_session, **kwargs)
        self.host = host
        self.port = port
        self.coroutine: Optional[asyncio.BaseTransport] = None

    def make_application(self) -> web.Application:
        """Construct the aiohttp application."""
        app = web.Application()
        app.add_routes([
            web.get('/', self.invite_message_handler),
            web.post('/', self.inbound_message_handler),
        ])
        return app

    async def start(self) -> None:
        """Start this transport.

        Raises:
            InboundTransportSetupError: If there was an error starting the webserver
        """
        loop = asyncio.get_event_loop()
        ssl_context = self.get_ssl_context()

        server = await loop.create_server(
            lambda: Http2ServerProtocol(self.make_application()),
            self.host,
            self.port,
            ssl=ssl_context,
        )
        self.coroutine = server

    async def stop(self) -> None:
        """Stop this transport."""
        if self.coroutine:
            self.coroutine.close()
            await self.coroutine.wait_closed()

    async def inbound_message_handler(self, request: web.Request):
        """Message handler for inbound messages.

        Args:
            request: aiohttp request object

        Returns:
            The web response
        """
        body = await request.read()

        client_info = {"host": request.host, "remote": request.remote}

        session = await self.create_session(
            accept_undelivered=True, can_respond=True, client_info=client_info
        )

        async with session:
            try:
                inbound = await session.receive(body)
            except (MessageParseError, WireFormatParseError):
                raise web.HTTPBadRequest()

            if inbound.receipt.direct_response_requested:
                await inbound.wait_processing_complete()
                response = (
                    await session.wait_response() if session.response_buffer else None
                )

                session.can_respond = False
                session.clear_response()

                if response:
                    if isinstance(response, bytes):
                        return web.Response(
                            body=response,
                            status=200,
                            content_type=(
                                DIDCOMM_V1_MIME_TYPE
                                if session.profile.settings.get(
                                    "emit_new_didcomm_mime_type"
                                )
                                else DIDCOMM_V0_MIME_TYPE
                            ),
                        )
                    else:
                        return web.Response(
                            text=response,
                            status=200,
                            content_type="application/json",
                        )
        return web.Response(status=200)

    async def invite_message_handler(self, request: web.Request):
        """Message handler for invites.

        Args:
            request: aiohttp request object

        Returns:
            The web response
        """
        if request.query.get("c_i"):
            return web.Response(
                text="You have received a connection invitation. To accept the "
                     "invitation, paste it into your agent application."
            )
        else:
            return web.Response(status=200)
