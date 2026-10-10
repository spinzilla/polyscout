import asyncio

import httpx

from polyscout.adapters import CSDNAdapter
from polyscout.transport import Transport


def run(handler, queries=("python",)):
    async def task():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = CSDNAdapter(Transport(client))
            records = []
            for query in queries:
                records.extend(await adapter.search(query))
            return records, adapter
    return asyncio.run(task())


def test_search_shell_is_gap_and_does_not_invent_article():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.host == "so.csdn.net"
        return httpx.Response(200, text="<html><div id='app'></div></html>", headers={"Content-Type": "text/html"})

    records, _ = run(handler)
    assert len(calls) == 1
    assert records[0].status == "unavailable"
    assert records[0].reason == "csdn_search_shell_no_article_links"


def test_article_meta_description_is_verbatim_bounded_excerpt():
    def handler(request):
        if request.url.host == "so.csdn.net":
            return httpx.Response(200, text='<a href="https://blog.csdn.net/u/article/details/123">Result</a>')
        return httpx.Response(200, text='<html><head><meta property="og:title" content="标题"><meta name="description" content="原文摘要 片段"></head></html>')

    records, _ = run(handler)
    assert records[0].status == "retrieved"
    assert records[0].excerpt == "原文摘要 片段"
    assert records[0].excerpt_kind == "api_fields"
    assert str(records[0].url) == "https://blog.csdn.net/u/article/details/123"


def test_521_opens_circuit_and_later_queries_do_not_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(521, text="Web Server Is Down")

    records, adapter = run(handler, ("one", "two"))
    assert len(calls) == 1
    assert records[0].status == "blocked"
    assert records[0].reason == "http_521"
    assert records[1].status == "blocked"
    assert records[1].reason == "circuit_open:http_521"


def test_login_wall_is_blocked_without_bypass():
    records, adapter = run(lambda request: httpx.Response(200, text="<html>请登录后继续</html>", headers={"Content-Type": "text/html"}))
    assert records[0].status == "blocked"
    assert adapter.wall_reason == "html_hard_wall"
