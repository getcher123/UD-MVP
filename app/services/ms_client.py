"""Client for external Microsoft service interactions."""

import httpx


class MSClient:
    """Minimal asynchronous HTTP client."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url)

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        await self._client.aclose()
