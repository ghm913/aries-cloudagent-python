import logging
import ssl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from hypercorn.asyncio import serve
from hypercorn.config import Config

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

    def make_application(self) -> Starlette:
        """Construct the Starlette application."""
        return Starlette(
            routes=[
                Route("/", self.invite_message_handler, methods=["GET"]),
                Route("/", self.inbound_message_handler, methods=["POST"]),
            ]
        )

    async def start(self) -> None:
        """Start this transport.

        Raises:
            InboundTransportSetupError: If there was an error starting the webserver
        """
        app = self.make_application()

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain('certs/ssl.crt', 'certs/ssl.key')

        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.certfile = 'certs/ssl.crt'
        config.keyfile = 'certs/ssl.key'
        config.alpn_protocols = ['h2', 'http/1.1']

        try:
            LOGGER.info(f"Server starting at https://{self.host}:{self.port}")
            await serve(app, config)
            LOGGER.info(f"Server started at https://{self.host}:{self.port}")
        except OSError as e:
            raise InboundTransportSetupError(
                f"Unable to start webserver with host '{self.host}' and port '{self.port}': {e}"
            )

    async def stop(self) -> None:
        """Stop this transport."""
        # Hypercorn's server stopping is handled by the server instance itself.
        pass

    async def inbound_message_handler(self, request: Request):
        """Message handler for inbound messages.

        Args:
            request: Starlette request object

        Returns:
            The web response
        """
        body = await request.body()

        client_info = {"host": request.url.netloc, "remote": request.client.host}

        session = await self.create_session(
            accept_undelivered=True, can_respond=True, client_info=client_info
        )

        async with session:
            try:
                inbound = await session.receive(body)
            except (MessageParseError, WireFormatParseError):
                return Response(status_code=400)

            if inbound.receipt.direct_response_requested:
                await inbound.wait_processing_complete()
                response = await session.wait_response() if session.response_buffer else None

                session.can_respond = False
                session.clear_response()

                if response:
                    if isinstance(response, bytes):
                        return Response(
                            content=response,
                            status_code=200,
                            headers={
                                "content-type": (
                                    DIDCOMM_V1_MIME_TYPE
                                    if session.profile.settings.get("emit_new_didcomm_mime_type")
                                    else DIDCOMM_V0_MIME_TYPE
                                )
                            },
                        )
                    else:
                        return Response(
                            content=response,
                            status_code=200,
                            headers={"content-type": "application/json"},
                        )
        return Response(status_code=200)

    async def invite_message_handler(self, request: Request):
        """Message handler for invites.

        Args:
            request: Starlette request object

        Returns:
            The web response
        """
        if request.query_params.get("c_i"):
            return Response(
                content="You have received a connection invitation. To accept the "
                        "invitation, paste it into your agent application.",
                status_code=200,
            )
        else:
            return Response(status_code=200)
