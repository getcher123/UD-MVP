from __future__ import annotations

from typing import Any, List, Dict


class AgentQLClient:
    """Stub client for AgentQL.

    Replace with real HTTP/SDK calls to AgentQL.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def run_query(self, pdf_bytes: bytes, query: str) -> List[Dict[str, Any]]:
        # TODO: Implement real call; returning dummy data for now
        return [{"row": 1, "value": "example"}]

