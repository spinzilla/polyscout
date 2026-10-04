import asyncio
import gzip
import json

import httpx
import pytest

from polyscout.adapters import GitHubAdapter, WebSearchAdapter
from polyscout.transport import Transport


def run_adapter(handler, factory, queries=("rtos",)):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = factory(Transport(client))
            result = []
            for query in queries:
                result.extend(await adapter.search(query))
            return result, adapter
    return asyncio.run(run())


def test_github_detail_overrules_search_snapshot_and_preserves_literal_fields():
    seen = []
    body = '{ "full_name" : "org/rtos", "archived" : true, "stargazers_count": 42, "private": false }'

    def handler(request):
        seen.append(request)
        assert "authorization" not in request.headers
        if request.url.path == "/search/repositories":
            assert request.url.params["q"] == "rtos"
            return httpx.Response(200, json={"items": [{"full_name": "org/rtos", "archived": False}]})
        assert request.url.path == "/repos/org/rtos"
        return httpx.Response(200, text=body)

    records, _ = run_adapter(handler, GitHubAdapter)
    assert len(seen) == 2
    assert records[0].credibility == "primary"
    assert '"archived" : true' in records[0].excerpt
    assert all(line in body for line in records[0].excerpt.splitlines())
    assert str(records[0].url) == "https://api.github.com/repos/org/rtos"


@pytest.mark.parametrize("code", [401, 403, 429, 302])
def test_wall_prevents_all_later_requests(code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code, headers={"Location": "https://example.com/login"})
    records, adapter = run_adapter(handler, GitHubAdapter, ("one", "two", "three"))
    assert len(calls) == 1
    assert all(e.status == "blocked" for e in records)
    assert adapter.wall_reason


def test_detail_wall_preserves_prior_evidence_and_stops_next_repository():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/search/repositories":
            return httpx.Response(200, json={"items": [{"full_name": f"o/{i}"} for i in range(3)]})
        if request.url.path == "/repos/o/0":
            return httpx.Response(200, json={"full_name": "o/0", "archived": True})
        return httpx.Response(403)
    records, _ = run_adapter(handler, GitHubAdapter, ("first", "second"))
    assert calls == ["/search/repositories", "/repos/o/0", "/repos/o/1"]
    assert records[0].status == "retrieved"
    assert all(e.status == "blocked" for e in records[1:])


@pytest.mark.parametrize("provider", ["tavily", "bing"])
def test_search_wire_protocol_and_verbatim_snippet(provider):
    def handler(request):
        assert "cookie" not in request.headers
        assert "search-secret" not in str(request.url)
        if provider == "tavily":
            assert request.method == "POST"
            assert request.headers["authorization"] == "Bearer search-secret"
            assert json.loads(request.content)["include_raw_content"] is False
            return httpx.Response(200, json={"results": [{"title": "A", "url": "https://example.com/a", "content": "Exact text\n第二行"}]})
        assert request.method == "GET"
        assert request.url.params["q"] == "rtos"
        assert request.headers["Ocp-Apim-Subscription-Key"] == "search-secret"
        return httpx.Response(200, json={"webPages": {"value": [{"name": "A", "url": "https://example.com/a", "snippet": "Exact text\n第二行"}]}})
    records, _ = run_adapter(handler, lambda t: WebSearchAdapter(t, provider, "https://search.example/api", "search-secret"))
    assert records[0].excerpt == "Exact text\n第二行"
    assert records[0].credibility == "secondary"


def test_html_captcha_and_json_wall_are_not_bypassed():
    for response in [httpx.Response(200, text="<html>CAPTCHA</html>", headers={"Content-Type": "text/html"}),
                     httpx.Response(200, json={"error": "risk control login required"})]:
        calls = []
        def handler(request):
            calls.append(request)
            return response
        records, _ = run_adapter(handler, GitHubAdapter, ("one", "two"))
        assert len(calls) == 1
        assert records[0].status == "blocked"


def test_three_failures_stop_without_retry():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503)
    records, _ = run_adapter(handler, GitHubAdapter, ("1", "2", "3", "4"))
    assert len(calls) == 3
    assert records[-1].reason == "consecutive_failure_limit"


def test_cookie_is_not_sent_even_if_provider_sets_one():
    calls = []
    def handler(request):
        calls.append(request)
        assert "cookie" not in request.headers
        return httpx.Response(200, json={"items": []}, headers={"Set-Cookie": "session=secret; Path=/"})
    run_adapter(handler, GitHubAdapter, ("one", "two"))
    assert len(calls) == 2


def test_missing_search_key_does_not_make_http_request():
    records, _ = run_adapter(lambda r: pytest.fail("HTTP attempted"), lambda t: WebSearchAdapter(t, "tavily", "https://api.example/search", ""))
    assert records[0].reason == "search_key_not_configured"


def test_invalid_search_items_are_gaps_and_excerpt_is_bounded():
    records, _ = run_adapter(lambda r: httpx.Response(200, json={"results": [
        {"url": "javascript:alert(1)", "content": "bad"},
        {"url": "https://example.com", "content": "a" * 5000},
        {"url": "https://example.com/empty", "content": ""},
    ]}), lambda t: WebSearchAdapter(t, "tavily", "https://api.example/search", "key-value"))
    assert [e.status for e in records] == ["unavailable", "retrieved", "unavailable"]
    assert len(records[1].excerpt) == 800


def test_compressed_response_and_network_error():
    records, _ = run_adapter(lambda r: httpx.Response(200, content=gzip.compress(b'{"items": []}'), headers={"Content-Encoding": "gzip"}), GitHubAdapter)
    assert records[0].reason == "no_results"
    def timeout(request):
        raise httpx.ReadTimeout("secret-body", request=request)
    records, _ = run_adapter(timeout, GitHubAdapter)
    assert records[0].reason == "network_error"


def test_malformed_and_oversized_responses():
    for response, reason in [(httpx.Response(200, text="not-json"), "invalid_json"),
                             (httpx.Response(200, json=[]), "invalid_payload"),
                             (httpx.Response(200, content=b"x" * 2_000_001), "response_too_large")]:
        records, _ = run_adapter(lambda r: response, GitHubAdapter)
        assert records[0].reason == reason


def test_wall_status_has_priority_over_body_size():
    records, _ = run_adapter(lambda r: httpx.Response(403, content=b"x" * 2_000_001), GitHubAdapter, ("first", "second"))
    assert all(record.status == "blocked" for record in records)
    assert records[0].reason == "http_403_wall"


def test_chinese_wall_message_and_headerless_html_stop_adapter():
    for response in (httpx.Response(200, json={"message": "请登录后继续"}),
                     httpx.Response(200, content=b"<html>Verify you are human</html>")):
        records, adapter = run_adapter(lambda r: response, GitHubAdapter)
        assert records[0].status == "blocked"
        assert adapter.wall_reason
