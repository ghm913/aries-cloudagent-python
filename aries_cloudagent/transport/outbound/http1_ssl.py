import logging
from typing import Union

import httpx

from ...core.profile import Profile

from ..stats import StatsTracer
from ..wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE

from .base import BaseOutboundTransport, OutboundTransportError


class Http2Transport(BaseOutboundTransport):
    """HTTP/2 outbound transport class."""

    schemes = ("http", "https")
    is_external = False

    def __init__(self, **kwargs) -> None:
        """Initialize an `Http2Transport` instance."""
        super().__init__(**kwargs)
        self.client: httpx.AsyncClient = None
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the transport."""
        self.client = httpx.AsyncClient(
            http2=False,
            verify="certs/ssl.crt"  # Use the provided certificate
        )
        return self

    async def stop(self):
        """Stop the transport."""
        await self.client.aclose()
        self.client = None

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
                headers["Content-Type"] = DIDCOMM_V1_MIME_TYPE
            else:
                headers["Content-Type"] = DIDCOMM_V0_MIME_TYPE
        else:
            headers["Content-Type"] = "application/json"
        self.logger.debug(
            "Posting to %s; Data: %s; Headers: %s", endpoint, payload, headers
        )
        response = await self.client.post(endpoint, content=payload, headers=headers)
        self.logger.info(f"HTTP version used: {response.http_version}")
        if response.status_code < 200 or response.status_code > 299:
            raise OutboundTransportError(
                (
                    f"Unexpected response status {response.status_code}, "
                    f"caused by: {response.reason_phrase}"
                )
            )
