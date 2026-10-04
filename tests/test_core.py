import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from polyscout.cli import app
from polyscout.config import Settings, endpoint
from polyscout.models import Claim, Observation, Synthesis
from polyscout.planner import research
from polyscout.store import EvidenceStore
from polyscout.synthesis import validate_citations


def settings(**kwargs):
    return Settings(llm_base_url="https://llm.example/v1", llm_api_key="llm-secret-value", llm_model="mock-model",
                    search_endpoint="https://search.example/api", search_api_key="search-secret-value", **kwargs)


def plan():
    return {"subquestions": ["maintenance", "context"], "queries": [
        {"adapter": "github", "query": "rtos archived:true", "purpose": "Check maintenance"},
        {"adapter": "websearch", "query": "RTOS maintenance status", "purpose": "Find context"},
    ]}


def chat(value):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}}], "usage": {"total_tokens": 42}})


def test_schema_requires_real_evidence_or_reason():
    with pytest.raises(ValidationError):
        Observation(adapter="github", query="q", status="retrieved")
    with pytest.raises(ValidationError):
        Observation(adapter="github", query="q", status="unavailable")
    with pytest.raises(ValidationError):
        Observation(adapter="github", query="q", status="blocked", reason="wall", excerpt="invented")


def test_store_roundtrip_unique_runs_and_integrity(tmp_path):
    store = EvidenceStore(tmp_path)
    record = store.add(Observation(adapter="github", query="q", status="retrieved", url="https://api.github.com/repos/a/b", excerpt='"archived": true', excerpt_kind="api_fields", credibility="primary"))
    store.add(Observation(adapter="websearch", query="q", status="blocked", reason="wall"))
    assert EvidenceStore.read(store.run_dir) == store.records
    assert record.id == "E0001"
    assert len(list((store.run_dir / "raw").iterdir())) == 1
    assert EvidenceStore(tmp_path).run_dir != store.run_dir
    (store.run_dir / record.raw_path).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        EvidenceStore.read(store.run_dir)


def test_citation_validation_rejects_missing_and_unavailable(tmp_path):
    store = EvidenceStore(tmp_path)
    store.add(Observation(adapter="websearch", query="q", status="unavailable", reason="failed"))
    for identifier in ("E0001", "E9999"):
        with pytest.raises(ValueError):
            validate_citations(Synthesis(claims=[Claim(text="claim", evidence_ids=[identifier], confidence="high", rationale="claimed")], gaps=[]), store.records)


def test_citation_validation_salvages_partially_valid_claims(tmp_path):
    # 打捞语义：混合引用剔除无效部分保留 claim；纯无效引用才丢弃并记入 gaps
    store = EvidenceStore(tmp_path)
    store.add(Observation(adapter="github", query="q", status="retrieved", url="https://api.github.com/repos/a/b",
                          excerpt='"archived": false', excerpt_kind="api_fields", credibility="primary"))
    store.add(Observation(adapter="websearch", query="q", status="unavailable", reason="wall"))
    result = Synthesis(claims=[
        Claim(text="mixed", evidence_ids=["E0001", "E0002"], confidence="high", rationale="r"),
        Claim(text="pure-invalid", evidence_ids=["E0002"], confidence="low", rationale="r"),
    ], gaps=[])
    out = validate_citations(result, store.records)
    assert [c.text for c in out.claims] == ["mixed"]
    assert out.claims[0].evidence_ids == ["E0001"]
    assert out.claims[0].confidence == "medium"
    assert any("dropped" in g for g in out.gaps)


def test_research_end_to_end_parallel_sources_and_confidence_caps(tmp_path):
    async def run():
        github_started, web_started = asyncio.Event(), asyncio.Event()
        calls = []
        async def handler(request):
            calls.append(request)
            if request.url.host == "llm.example":
                body = json.loads(request.content)
                assert body["model"] == "mock-model"
                data = json.loads(body["messages"][1]["content"])
                if "round" in data:
                    return chat(plan())
                return chat({"claims": [
                    {"text": "The repository is archived.", "evidence_ids": ["E0001"], "confidence": "high", "rationale": "API field"},
                    {"text": "Search describes maintenance concerns.", "evidence_ids": ["E0002"], "confidence": "high", "rationale": "Search result"},
                ], "gaps": []})
            if request.url.path == "/search/repositories":
                github_started.set()
                await asyncio.wait_for(web_started.wait(), 2)
                return httpx.Response(200, json={"items": [{"full_name": "o/repo"}]})
            if request.url.host == "search.example":
                web_started.set()
                await asyncio.wait_for(github_started.wait(), 2)
                return httpx.Response(200, json={"results": [{"title": "Context", "url": "https://example.com", "content": "Maintenance concerns."}]})
            return httpx.Response(200, json={"full_name": "o/repo", "archived": True})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await research("Which RTOS?", settings(), tmp_path, client=client)
            assert not client.is_closed
        return result, calls
    result, calls = asyncio.run(run())
    assert result.requests == {"llm": 2, "github": 2, "websearch": 1}
    records = EvidenceStore.read(result.run_dir)
    assert len(records) == 2
    report = (result.run_dir / "report.md").read_text(encoding="utf-8")
    assert "Confidence: medium" in report and "Confidence: low" in report
    assert "[E0001](#e0001)" in report
    assert json.loads((result.run_dir / "run.json").read_text())["llm_usage"]["reported_total_tokens"] == 84
    for path in result.run_dir.rglob("*"):
        if path.is_file():
            assert "secret-value" not in path.read_text(encoding="utf-8")


def test_invalid_llm_and_hard_walls_produce_auditable_partial_report(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.host == "llm.example":
            return httpx.Response(200, json={"choices": []})
        return httpx.Response(403)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research("RTOS", settings(), tmp_path, client=client)
    result = asyncio.run(run())
    assert result.status == "partial"
    assert len(calls) == 3
    assert all(e.status == "blocked" for e in EvidenceStore.read(result.run_dir))
    assert "Insufficient evidence" in (result.run_dir / "report.md").read_text(encoding="utf-8")


def test_fabricated_citations_trigger_extractive_fallback(tmp_path):
    def handler(request):
        if request.url.host == "llm.example":
            data = json.loads(json.loads(request.content)["messages"][1]["content"])
            if "round" in data:
                return chat(plan())
            return chat({"claims": [{"text": "Fabricated conclusion", "evidence_ids": ["E9999"], "confidence": "high", "rationale": "none"}], "gaps": []})
        if request.url.path == "/search/repositories":
            return httpx.Response(200, json={"items": [{"full_name": "o/repo"}]})
        if request.url.host == "search.example":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"archived": True})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research("RTOS", settings(), tmp_path, client=client, max_rounds=1)
    result = asyncio.run(run())
    report = (result.run_dir / "report.md").read_text(encoding="utf-8")
    assert "Fabricated conclusion" not in report and "E9999" not in report
    assert "Extractive fallback" in report


def test_cancellation_cleans_up_tasks_and_records_status(tmp_path):
    async def run():
        started = asyncio.Event()
        active = 0
        async def handler(request):
            nonlocal active
            if request.url.host == "llm.example":
                return chat(plan())
            active += 1
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(research("RTOS", settings(), tmp_path, client=client))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert active == 0
            manifest = next(tmp_path.glob("*/run.json"))
            assert json.loads(manifest.read_text())["status"] == "cancelled"
            assert (manifest.parent / "report.md").exists()
    asyncio.run(run())


@pytest.mark.parametrize("value", ["https://user:password@example.com", "https://example.com?key=secret", "http://example.com", "file:///a"])
def test_bad_endpoint_rejected(value):
    with pytest.raises(ValueError):
        endpoint(value)


def test_cli_help_and_missing_config(monkeypatch):
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["research", "--help"]).exit_code == 0
    monkeypatch.delenv("POLYSCOUT_LLM_BASE_URL", raising=False)
    result = runner.invoke(app, ["research", "test"])
    assert result.exit_code == 2
    assert "POLYSCOUT_LLM_BASE_URL" in result.output


def test_cli_research_creates_run_under_mock_http(tmp_path, monkeypatch):
    import httpx
    original_client = httpx.AsyncClient
    def handler(request):
        if request.url.host == "llm.example":
            return chat(plan())
        return httpx.Response(403)
    monkeypatch.setenv("POLYSCOUT_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("POLYSCOUT_LLM_API_KEY", "mock-key-cli")
    monkeypatch.setenv("POLYSCOUT_LLM_MODEL", "mock-model")
    monkeypatch.setenv("POLYSCOUT_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("POLYSCOUT_SEARCH_ENDPOINT", "https://search.example/api")
    monkeypatch.setenv("POLYSCOUT_SEARCH_API_KEY", "mock-search-key-cli")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    result = CliRunner().invoke(app, ["research", "RTOS", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Status: partial" in result.output
    assert len(list(tmp_path.glob("*/report.md"))) == 1


def test_followup_is_bounded_and_deduplicates_queries(tmp_path):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == "llm.example":
            return chat(plan())
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"results": []})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research("RTOS", settings(), tmp_path, client=client)
    result = asyncio.run(run())
    assert calls.count("llm.example") == 2
    assert calls.count("api.github.com") == calls.count("search.example") == 1
    assert "No new queries" in (result.run_dir / "report.md").read_text(encoding="utf-8")


def test_sensitive_source_is_a_gap_not_persisted(tmp_path):
    def handler(request):
        if request.url.host == "llm.example":
            return chat(plan())
        if request.url.host == "search.example":
            return httpx.Response(200, json={"results": [{"url": "https://example.com", "content": "search-secret-value"}]})
        return httpx.Response(403)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research("RTOS", settings(), tmp_path, client=client, max_rounds=1)
    result = asyncio.run(run())
    assert any(e.reason == "sensitive_source_content_omitted" for e in EvidenceStore.read(result.run_dir))
    for path in result.run_dir.rglob("*"):
        if path.is_file():
            assert "search-secret-value" not in path.read_text(encoding="utf-8")


def test_cancellation_retains_already_completed_source_batch(tmp_path):
    async def run():
        completed = asyncio.Event()
        async def handler(request):
            if request.url.host == "llm.example":
                return chat(plan())
            if request.url.path == "/search/repositories":
                return httpx.Response(200, json={"items": [{"full_name": "o/repo"}]})
            if request.url.path == "/repos/o/repo":
                completed.set()
                return httpx.Response(200, json={"archived": True})
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(research("RTOS", settings(), tmp_path, client=client))
            await asyncio.wait_for(completed.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        records = EvidenceStore.read(next(tmp_path.iterdir()))
        assert len(records) == 1 and records[0].status == "retrieved"
    asyncio.run(run())


def test_offline_guard_blocks_loopback_outside_event_loop_socketpair():
    import socket
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="forbidden"):
            sock.connect(("127.0.0.1", 80))


def test_llm_temperature_omitted_unless_configured():
    # 回归：kimi-k3 等端点拒绝自定义 temperature，缺省必须不携带该字段
    from polyscout.llm import LLM
    from polyscout.models import Plan
    from polyscout.transport import Transport

    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return chat(plan())

    async def run(temp):
        s = settings() if temp is None else settings(llm_temperature=temp)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await LLM(s, Transport(client)).ask("plan", {"question": "q"}, Plan)

    asyncio.run(run(None))
    asyncio.run(run(0.2))
    assert "temperature" not in bodies[0]
    assert bodies[1]["temperature"] == 0.2


def test_llm_strips_markdown_code_fence():
    # 回归：模型把 JSON 套进 ```json 围栏时仍能解析
    from polyscout.llm import LLM, strip_code_fence
    from polyscout.models import Plan
    from polyscout.transport import Transport

    assert strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'

    fenced = json.dumps(plan())
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": f"```json\n{fenced}\n```"}}], "usage": {"total_tokens": 1}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await LLM(settings(), Transport(client)).ask("plan", {"question": "q"}, Plan)
            assert result.subquestions
    asyncio.run(run())


def test_llm_uses_longer_configurable_timeout():
    # 回归：推理模型响应常超 20s，LLM 调用必须用可配置的长超时
    from polyscout.llm import LLM
    from polyscout.models import Plan
    from polyscout.transport import Transport

    seen = []
    def handler(request):
        seen.append(request.extensions.get("timeout"))
        return chat(plan())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await LLM(settings(llm_timeout=321), Transport(client)).ask("plan", {"question": "q"}, Plan)
    asyncio.run(run())
    assert seen and seen[0].get("connect") is not None
    assert all(v == 321 for v in seen[0].values())
