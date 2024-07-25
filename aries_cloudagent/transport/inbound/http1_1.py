import logging
from aiohttp import web
import ssl

from ...messaging.error import MessageParseError
from ..error import WireFormatParseError
from ..wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE
from .base import BaseInboundTransport, InboundTransportSetupError

LOGGER = logging.getLogger(__name__)

class Http2Transport(BaseInboundTransport):
    """HTTP/2 Transport class."""

    def __init__(self, host: str, port: int, create_session, **kwargs) -> None:
        """Initialize an inbound HTTP/2 transport instance.

        Args:
            host: Host to listen on
            port: Port to listen on
            create_session: Method to create a new inbound session
        """
        super().__init__("http2", create_session, **kwargs)
        self.host = host
        self.port = port
        self.runner = None

    async def make_application(self) -> web.Application:
        """Construct the aiohttp application."""
        app_args = {}
        if self.max_message_size:
            app_args["client_max_size"] = self.max_message_size
        app = web.Application(**app_args)
        app.add_routes([web.get("/", self.invite_message_handler)])
        app.add_routes([web.post("/", self.inbound_message_handler)])
        return app

    async def start(self) -> None:
        """Start this transport.

        Raises:
            InboundTransportSetupError: If there was an error starting the webserver
        """
        app = await self.make_application()

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain('certs/ssl.crt', 'certs/ssl.key')

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port, ssl_context=ssl_context)
        self.runner = runner

        try:
            await site.start()
            LOGGER.info(f"Server started at https://{self.host}:{self.port}")
        except OSError as e:
            raise InboundTransportSetupError(
                f"Unable to start webserver with host '{self.host}' and port '{self.port}': {e}"
            )

    async def stop(self) -> None:
        """Stop this transport."""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

    async def inbound_message_handler(self, request: web.BaseRequest):
        """Message handler for inbound messages.

        Args:
            request: aiohttp request object

        Returns:
            The web response
        """
        ctype = request.headers.get("content-type", "")
        if ctype.split(";", 1)[0].lower() == "application/json":
            body = await request.text()
        else:
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
                response = await session.wait_response() if session.response_buffer else None

                session.can_respond = False
                session.clear_response()

                if response:
                    if isinstance(response, bytes):
                        return web.Response(
                            body=response,
                            status=200,
                            headers={
                                "Content-Type": (
                                    DIDCOMM_V1_MIME_TYPE
                                    if session.profile.settings.get("emit_new_didcomm_mime_type")
                                    else DIDCOMM_V0_MIME_TYPE
                                )
                            },
                        )
                    else:
                        return web.Response(
                            text=response,
                            status=200,
                            headers={"Content-Type": "application/json"},
                        )
        return web.Response(status=200)

    async def invite_message_handler(self, request: web.BaseRequest):
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
