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


# ---------------- Bilibili adapter (v0.2) ----------------

from polyscout.adapters import BilibiliAdapter
from polyscout.adapters.bilibili import COOKIE_BUDGET, wbi_sign

_NAV = {"code": -101, "data": {"wbi_img": {
    "img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 32 + ".png",
    "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 32 + ".png"}}}
_VIEW = {"code": 0, "data": {"cid": 123, "title": "STM32 入门教程", "desc": "零基础讲解",
                              "duration": 600, "pubdate": 1700000000, "owner": {"name": "某UP"}}}
_SUBS = {"code": 0, "data": {"subtitle": {"subtitles": [
    {"lan": "en", "lan_doc": "English", "subtitle_url": "//cdn.example/en.json"},
    {"lan": "zh-CN", "lan_doc": "中文（自动生成）", "subtitle_url": "//cdn.example/zh.json"}]}}}
_ZH_BODY = {"body": [{"from": 0.0, "to": 1.5, "content": "大家好，这里是第一课"},
                     {"from": 1.5, "to": 3.0, "content": "今天我们讲寄存器"}]}


def _bilibili_handler(search_payload, player_payload=_SUBS, sub_payload=_ZH_BODY, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        path = request.url.path
        if path == "/x/web-interface/nav":
            return httpx.Response(200, json=_NAV)
        if path == "/x/web-interface/wbi/search/type":
            assert request.url.params["w_rid"] and request.url.params["wts"]
            return httpx.Response(200, json=search_payload)
        if path == "/x/web-interface/view":
            return httpx.Response(200, json=_VIEW)
        if path == "/x/player/v2":
            return httpx.Response(200, json=player_payload)
        if request.url.host == "cdn.example":
            return httpx.Response(200, json=sub_payload)
        return httpx.Response(404)
    return handler


def test_bilibili_wbi_sign_matches_public_algorithm():
    import hashlib
    from urllib.parse import urlencode
    img, sub = "a" * 32, "b" * 32
    raw = img + sub
    from polyscout.adapters.bilibili import MIXIN_KEY_ENC_TAB
    mixin = "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]
    signed = wbi_sign({"keyword": "rtos", "page": 1}, img, sub)
    check = {k: v for k, v in signed.items() if k != "w_rid"}
    assert signed["w_rid"] == hashlib.md5((urlencode(sorted(check.items())) + mixin).encode()).hexdigest()


def test_bilibili_happy_path_subtitle_verbatim_and_byo_cookie():
    seen = []
    search = {"code": 0, "message": "0", "data": {"result": [{"bvid": "BV1xx411c7mD"}]}}
    records, _ = run_adapter(_bilibili_handler(search, seen=seen),
                             lambda t: BilibiliAdapter(t, "sess-secret"))
    assert records[0].status == "retrieved"
    assert records[0].excerpt_kind == "subtitle_excerpt"
    assert records[0].excerpt == "大家好，这里是第一课\n今天我们讲寄存器"  # 中文轨优先于英文轨
    assert str(records[0].url) == "https://www.bilibili.com/video/BV1xx411c7mD"
    authed = [r for r in seen if "SESSDATA=sess-secret" in r.headers.get("cookie", "")]
    assert {r.url.path if r.url.host != "cdn.example" else "cdn" for r in authed} == {"/x/player/v2", "cdn"}
    assert all("sess-secret" not in str(r.url) for r in seen)


def test_bilibili_anonymous_degrades_to_metadata_without_cookie():
    seen = []
    search = {"code": 0, "data": {"result": [{"bvid": "BV1xx411c7mD"}]}}
    empty = {"code": 0, "data": {"subtitle": {"subtitles": []}}}
    records, _ = run_adapter(_bilibili_handler(search, player_payload=empty, seen=seen),
                             BilibiliAdapter)
    assert records[0].status == "retrieved"
    assert records[0].excerpt_kind == "api_fields"
    assert '"title": "STM32 入门教程"' in records[0].excerpt
    assert all("cookie" not in r.headers for r in seen)


def test_bilibili_risk_control_is_hard_wall_and_circuits():
    for code in (-352, -412):
        calls = []
        search = {"code": code, "message": "risk"}
        records, adapter = run_adapter(_bilibili_handler(search, seen=calls),
                                       BilibiliAdapter, ("one", "two"))
        assert len(calls) == 2  # nav + 首次搜索；熔断后零网络
        assert records[0].status == "blocked" and records[0].reason == f"bilibili_risk_control_{-code}"
        assert records[1].reason.startswith("circuit_open:")


def test_bilibili_business_error_is_not_a_wall():
    search = {"code": -400, "message": "bad request"}
    records, adapter = run_adapter(_bilibili_handler(search), BilibiliAdapter)
    assert records[0].status == "unavailable" and records[0].reason == "bilibili_error_400"
    assert not adapter.wall_reason


def test_bilibili_cookie_budget_downgrades_later_requests(monkeypatch):
    seen = []
    monkeypatch.setattr("polyscout.adapters.bilibili.COOKIE_BUDGET", 1)
    search = {"code": 0, "data": {"result": [{"bvid": "BV1xx411c7mD"}]}}
    records, adapter = run_adapter(_bilibili_handler(search, seen=seen),
                                   lambda t: BilibiliAdapter(t, "sess-secret"))
    assert records[0].status == "retrieved"
    cookie_hits = [r for r in seen if "SESSDATA" in r.headers.get("cookie", "")]
    assert len(cookie_hits) == 1 and cookie_hits[0].url.path == "/x/player/v2"
    assert adapter._cookie_used == 1


def test_bilibili_invalid_bvid_and_expired_cookie_fallback():
    search = {"code": 0, "data": {"result": [{"bvid": "not-a-bvid"}, {"bvid": "BV1xx411c7mD"}]}}
    expired = {"code": -101, "message": "not logged in"}
    records, _ = run_adapter(_bilibili_handler(search, player_payload=expired),
                             lambda t: BilibiliAdapter(t, "sess-secret"))
    assert records[0].reason == "bilibili_invalid_bvid"
    assert records[1].status == "retrieved" and records[1].excerpt_kind == "api_fields"


def test_bilibili_transport_cookie_opt_in_only():
    # 默认路径不变：不显式申请 cookies 的 adapter 绝不外发 cookie（现有契约回归）
    def handler(request):
        assert "cookie" not in request.headers
        return httpx.Response(200, json={"items": []})
    run_adapter(handler, GitHubAdapter)
