import logging
import ssl
from typing import Union, cast
from urllib.parse import urlparse

from aioquic.asyncio import connect
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration

from .http3_client import Http3Client
from .base import BaseOutboundTransport, OutboundTransportError
from ..wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE
from ...core.profile import Profile


class Http3Transport(BaseOutboundTransport):
    """Http3 outbound transport class."""

    schemes = ("https")
    is_external = False

    def __init__(self, **kwargs) -> None:
        """Initialize an `Http3Transport` instance."""
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.connection_pool = {}

    async def start(self):
        """Start the transport."""
        return self

    async def stop(self):
        """Stop the transport."""
        for client in self.connection_pool.values():
            await client.close()
        self.connection_pool.clear()

    async def get_client(self, host, port) -> Http3Client:
        """Get or create a QUIC client."""
        key = f"{host}:{port}"
        if key not in self.connection_pool:
            configuration = QuicConfiguration(
                is_client=True,
                alpn_protocols=H3_ALPN,
                verify_mode=ssl.CERT_NONE,
            )
            client = await connect(
                host,
                port,
                configuration=configuration,
                create_protocol=Http3Client,
            )
            self.connection_pool[key] = cast(Http3Client, client)
        return self.connection_pool[key]

    async def handle_message(
        self,
        profile: Profile,
        payload: Union[str, bytes],
        endpoint: str,
        metadata: dict = None,
        api_key: str = None,
    ):
        """Handle message from queue.

        Args:
            profile: the profile that produced the message
            payload: message payload in string or byte format
            endpoint: URI endpoint for delivery
            metadata: Additional metadata associated with the payload
        """
        if not endpoint:
            raise OutboundTransportError("No endpoint provided")
        headers = metadata or {}
        if api_key is not None:
            headers["x-api-key"] = api_key
        if isinstance(payload, bytes):
            if profile.settings.get("emit_new_didcomm_mime_type"):
                headers["content-type"] = DIDCOMM_V1_MIME_TYPE
            else:
                headers["content-type"] = DIDCOMM_V0_MIME_TYPE
        else:
            headers["content-type"] = "application/json"
        self.logger.debug(
            "Posting to %s; Data: %s; Headers: %s", endpoint, payload, headers
        )

        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port or 443

        client = await self.get_client(host, port)
        headers["content-length"] = str(len(payload))
        return await client.send_http_request(endpoint, "POST", payload, headers)
