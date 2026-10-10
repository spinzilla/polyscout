"""Minimal stdio MCP server for bounded, evidence-bearing source queries."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from polyscout.adapters import BilibiliAdapter, CSDNAdapter, GitHubAdapter, WebSearchAdapter
from polyscout.config import endpoint
from polyscout.transport import Transport


_ADAPTERS = ("github", "websearch", "bilibili", "csdn")
_SAFE_ERROR = "request_failed"


def _safe_endpoint(value: str, fallback: str) -> str:
    try:
        return endpoint(value)
    except (TypeError, ValueError):
        return fallback


class MCPRuntime:
    """Owns one transport and one adapter instance per stdio process."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=20, trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=2),
        )
        self.transport = Transport(self.client)
        provider = os.getenv("POLYSCOUT_SEARCH_PROVIDER", "tavily")
        if provider not in {"tavily", "bing"}:
            provider = "tavily"
        default_search = "https://api.tavily.com/search"
        search_url = _safe_endpoint(os.getenv("POLYSCOUT_SEARCH_ENDPOINT", default_search), default_search)
        self.adapters = {
            "github": GitHubAdapter(self.transport, os.getenv("POLYSCOUT_GITHUB_TOKEN", "")),
            "websearch": WebSearchAdapter(
                self.transport, provider, search_url, os.getenv("POLYSCOUT_SEARCH_API_KEY", "")),
            "bilibili": BilibiliAdapter(self.transport, os.getenv("POLYSCOUT_BILIBILI_SESSDATA", "")),
            "csdn": CSDNAdapter(self.transport),
        }
        self._secrets = tuple(value for value in (
            os.getenv("POLYSCOUT_SEARCH_API_KEY", ""),
            os.getenv("POLYSCOUT_GITHUB_TOKEN", ""),
            os.getenv("POLYSCOUT_BILIBILI_SESSDATA", ""),
        ) if value)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _scrub(self, value: Any) -> str:
        text = str(value)
        for secret in self._secrets:
            text = text.replace(secret, "[redacted]")
        text = re.sub(r"(?i)(authorization|cookie|sessdata|api[_-]?key|token|secret)\s*[:=]\s*[^\s,;]+",
                      r"\1=[redacted]", text)
        return text

    async def quick_search(self, adapter: str, query: str) -> list[dict[str, Any]]:
        if adapter not in self.adapters:
            raise ValueError("unknown_adapter")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("invalid_query")
        try:
            observations = await self.adapters[adapter].search(query.strip())
            return [
                {"id": f"E{index:04d}", **observation.model_dump(mode="json")}
                for index, observation in enumerate(observations, 1)
            ]
        except Exception as exc:  # MCP boundary: never expose provider/client details.
            raise RuntimeError(_SAFE_ERROR) from None

    def get_sources(self) -> list[dict[str, Any]]:
        return [
            {
                "adapter": name,
                "declaration": self.adapters[name].declaration.model_dump(mode="json"),
                "wall_reason": self._scrub(self.adapters[name].wall_reason),
                "failures": self.adapters[name].failures,
                "circuit_open": bool(self.adapters[name].wall_reason),
            }
            for name in _ADAPTERS
        ]


def create_server(runtime: MCPRuntime | None = None) -> tuple[MCPServer, MCPRuntime]:
    runtime = runtime or MCPRuntime()
    server = MCPServer(name="polyscout", version="0.3b")

    @server.tool(name="quick_search", description="Run one bounded read-only query against one source adapter.")
    async def quick_search(adapter: str, query: str) -> list[dict[str, Any]]:
        """Return local evidence IDs, verbatim excerpts, links and gap statuses."""
        return await runtime.quick_search(adapter, query)

    @server.tool(name="get_sources", description="Return adapter declarations and current circuit state.")
    async def get_sources() -> list[dict[str, Any]]:
        return runtime.get_sources()

    return server, runtime


async def main() -> None:
    server, runtime = create_server()
    try:
        await server.run_stdio_async()
    finally:
        await runtime.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
