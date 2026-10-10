import asyncio

import httpx

from polyscout.mcp import MCPRuntime, create_server
from polyscout.transport import Transport


def test_mcp_exposes_only_two_tools():
    async def run():
        server, runtime = create_server(MCPRuntime(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))))
        try:
            tools = await server.list_tools()
            return [tool.name for tool in tools]
        finally:
            await runtime.client.aclose()

    assert asyncio.run(run()) == ["quick_search", "get_sources"]


def test_quick_search_returns_local_ids_and_gap_without_secret():
    def handler(request):
        assert "cookie" not in request.headers
        return httpx.Response(200, text="<html><div id='app'></div></html>")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            runtime = MCPRuntime(client)
            result = await runtime.quick_search("csdn", "python")
            return result, runtime.get_sources()

    records, sources = asyncio.run(run())
    assert records[0]["id"] == "E0001"
    assert records[0]["status"] == "unavailable"
    assert records[0]["reason"] == "csdn_search_shell_no_article_links"
    assert {item["adapter"] for item in sources} == {"github", "websearch", "bilibili", "csdn"}
    assert all("declaration" in item and "compliance" in item["declaration"] for item in sources)


def test_mcp_errors_are_fixed_and_do_not_echo_credentials(monkeypatch):
    monkeypatch.setenv("POLYSCOUT_SEARCH_API_KEY", "super-secret-key")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
            runtime = MCPRuntime(client)
            try:
                await runtime.quick_search("unknown", "super-secret-key")
            except Exception as exc:
                return str(exc)
        return ""

    error = asyncio.run(run())
    assert error == "unknown_adapter"
    assert "super-secret-key" not in error
