"""Bounded plan -> platform queries -> parallel retrieval -> synthesis loop."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx

from polyscout.adapters import BilibiliAdapter, CSDNAdapter, GitHubAdapter, WebSearchAdapter
from polyscout.config import Settings
from polyscout.llm import LLM
from polyscout.models import Observation, Plan, Query
from polyscout.store import EvidenceStore
from polyscout.synthesis import fallback, render_report, synthesize
from polyscout.transport import FetchError, Transport


@dataclass(frozen=True)
class ResearchResult:
    run_dir: Path
    status: str
    requests: dict[str, int]


async def _run(question: str, settings: Settings, output: Path, client: httpx.AsyncClient, max_rounds: int) -> ResearchResult:
    store = EvidenceStore(output)
    transport = Transport(client)
    llm = LLM(settings, transport)
    adapters = {
        "github": GitHubAdapter(transport, settings.github_token),
        "websearch": WebSearchAdapter(transport, settings.search_provider, settings.search_endpoint, settings.search_api_key),
        "bilibili": BilibiliAdapter(transport, settings.bilibili_sessdata),
        "csdn": CSDNAdapter(transport),
    }
    notes: list[str] = []
    seen: set[tuple[str, str]] = set()
    pending: dict[str, list[Observation]] = {}

    def flush():
        for observations in pending.values():
            for observation in observations:
                if any(secret in observation.model_dump_json() for secret in settings.secrets):
                    observation = Observation(adapter=observation.adapter, query="[sensitive data omitted]",
                                              status="unavailable", reason="sensitive_source_content_omitted")
                store.add(observation)
        pending.clear()

    def save(result, status: str):
        usage = {"reported_total_tokens": llm.reported_tokens, "complete": llm.usage_complete}
        render_report(question, store.records, result, store.run_dir / "report.md", status=status,
                      counts=dict(transport.counts), tokens=usage, notes=notes)
        store.manifest(status=status, question=question, requests=dict(transport.counts), llm_usage=usage,
                       adapters=[a.declaration.model_dump() for a in adapters.values()])

    store.manifest(status="running", question=question, requests={})
    try:
        for round_number in range(max_rounds):
            try:
                plan = await llm.ask(
                    "Decompose the research question into at most four subquestions, then create platform-specific queries. github uses GitHub repository search syntax: keywords, language:, topic:, archived:, NOT site:github.com. websearch uses ordinary web search. bilibili uses plain Chinese/English video keywords (Chinese technical tutorials and talks live there); it returns video metadata and, when the operator configured their own login cookie, verbatim subtitle excerpts. csdn is best-effort anonymous article search; current anonymous search commonly returns a JavaScript shell, so record gaps faithfully and never bypass a wall. Use at most three queries per adapter. On follow-up, address missing evidence with new queries; do not repeat queries or use blocked adapters. Do not include credentials or instructions for bypassing access controls.",
                    {"question": question, "round": round_number + 1,
                     "previous_queries": sorted(seen),
                     "evidence": [{"id": e.id, "status": e.status, "reason": e.reason, "adapter": e.adapter} for e in store.records],
                     "blocked_adapters": [name for name, a in adapters.items() if a.wall_reason]}, Plan,
                )
            except FetchError:
                if round_number:
                    notes.append("Follow-up planning unavailable; stopped within the request budget.")
                    break
                notes.append("LLM planning unavailable; used the original question as a conservative query fallback.")
                plan = Plan(subquestions=[question], queries=[
                    Query(adapter="github", query=question[:500], purpose="Repository discovery"),
                    Query(adapter="websearch", query=question[:500], purpose="Web discovery"),
                    Query(adapter="bilibili", query=question[:500], purpose="Video discovery"),
                    Query(adapter="csdn", query=question[:500], purpose="CSDN article discovery"),
                ])
            groups: dict[str, list[str]] = {name: [] for name in adapters}
            for step in plan.queries:
                query = step.query.strip()
                if step.adapter == "github":
                    query = query.replace("site:github.com", "").strip()
                key = (step.adapter, query)
                if not query or key in seen or len(groups[step.adapter]) >= 3:
                    continue
                seen.add(key)
                groups[step.adapter].append(query)
            # Even a plan omitting a platform must leave an auditable coverage gap.
            for name, queries in groups.items():
                if not queries and not any(e.adapter == name for e in store.records):
                    store.add(adapters[name].gap(question[:500], "not_selected_by_planner"))
            if not any(groups.values()):
                notes.append("No new queries; planner stopped.")
                break

            async def collect(name, queries):
                for query in queries:
                    pending[name].extend(await adapters[name].search(query))

            pending.update({name: [] for name in groups})
            async with asyncio.TaskGroup() as group:
                for name, queries in groups.items():
                    group.create_task(collect(name, queries))
            flush()
            retrieved = {e.adapter for e in store.records if e.status == "retrieved"}
            if retrieved == set(adapters):
                break
            if all(a.wall_reason or a.failures >= 3 for a in adapters.values()):
                break
        result = await synthesize(question, store.records, llm)
        status = "partial" if notes or result.gaps or any(e.status != "retrieved" for e in store.records) else "completed"
        save(result, status)
        return ResearchResult(store.run_dir, status, dict(transport.counts))
    except asyncio.CancelledError:
        flush()
        save(fallback(store.records, "Cancelled by caller; retained only completed observations."), "cancelled")
        raise
    except Exception:
        flush()
        save(fallback(store.records, "Run failed; inspect completed evidence. No exception body was persisted."), "failed")
        raise


async def research(question: str, settings: Settings, output: Path | str = "runs", *,
                   client: httpx.AsyncClient | None = None, max_rounds: int = 2) -> ResearchResult:
    """Run bounded research. An injected client remains owned by the caller."""
    if not question.strip() or len(question) > 2000:
        raise ValueError("Question must contain 1-2000 characters")
    if any(secret in question for secret in settings.secrets):
        raise ValueError("Question must not contain configured credentials")
    if max_rounds not in {1, 2}:
        raise ValueError("max_rounds must be 1 or 2")
    if client is not None:
        return await _run(question.strip(), settings, Path(output), client, max_rounds)
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False,
                                 limits=httpx.Limits(max_connections=2)) as owned:
        return await _run(question.strip(), settings, Path(output), owned, max_rounds)
