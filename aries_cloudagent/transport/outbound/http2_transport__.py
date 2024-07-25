import logging
from typing import Union
from urllib.parse import urlparse

from .http2_client import Http2Client
from .base import BaseOutboundTransport, OutboundTransportError
from ..wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE
from ...core.profile import Profile

class Http2Transport(BaseOutboundTransport):
    """Http2 outbound transport class."""

    schemes = ("https")
    is_external = False

    def __init__(self, **kwargs) -> None:
        """Initialize an `Http2Transport` instance."""
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the transport."""
        return self

    async def stop(self):
        """Stop the transport."""
        pass

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

        client = Http2Client()

        await client.connect(host, port)

        headers["content-length"] = str(len(payload))
        response_data, response_headers = await client.send_http_request(endpoint, "POST", payload, headers)

        await client.close()

        return response_data, response_headers
