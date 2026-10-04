"""Grounded report generation with structural citation checks and confidence caps."""

import html
import re
from pathlib import Path

from polyscout.llm import LLM
from polyscout.models import Claim, Evidence, Synthesis
from polyscout.transport import FetchError


def fallback(records: list[Evidence], reason: str) -> Synthesis:
    return Synthesis(
        claims=[Claim(
            text=f"Retrieved an excerpt from {e.title or e.adapter}; inspect the quoted evidence below.",
            evidence_ids=[e.id], confidence="low",
            rationale="Extractive fallback only; no synthesized inference was verified.",
        ) for e in records if e.status == "retrieved"][:20],
        gaps=[reason],
    )


def validate_citations(result: Synthesis, records: list[Evidence]) -> Synthesis:
    lookup = {e.id: e for e in records if e.status == "retrieved"}
    if not result.claims and lookup:
        raise ValueError("No supported claims returned")
    for claim in result.claims:
        if any(key not in lookup for key in claim.evidence_ids):
            raise ValueError("Citation refers to missing or unavailable evidence")
        claim.evidence_ids = list(dict.fromkeys(claim.evidence_ids))
        # Credibility describes provenance, not proof that an inferred claim is true.
        if any(lookup[key].credibility != "primary" for key in claim.evidence_ids):
            claim.confidence = "low"
        elif claim.confidence == "high":
            claim.confidence = "medium"
        claim.rationale += " [v0.1 cap: primary API evidence <= medium; search snippets <= low.]"
    return result


async def synthesize(question: str, records: list[Evidence], llm: LLM) -> Synthesis:
    if not any(e.status == "retrieved" for e in records):
        return Synthesis(claims=[], gaps=["Insufficient evidence: no usable source excerpts were obtained."])
    try:
        result = await llm.ask(
            "Synthesize an evidence-based answer to the research question. Every factual claim must cite provided retrieved evidence IDs. Never invent IDs, quotes or facts. Distinguish search snippets from directly observed API fields. Record missing coverage, contradictions and unavailable sources in gaps. A citation does not prove entailment. Use cautious language and low confidence when support is weak.",
            {"question": question, "evidence": [e.model_dump(mode="json", exclude={"raw_path", "excerpt_sha256"}) for e in records]},
            Synthesis,
        )
        return validate_citations(result, records)
    except (FetchError, ValueError):
        return fallback(records, "Synthesis unavailable or invalid; showing retrieved excerpts without inferred conclusions.")


def safe_text(value: str) -> str:
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def render_report(question: str, records: list[Evidence], result: Synthesis,
                  path: Path, *, status: str, counts: dict, tokens: dict, notes: list[str]) -> None:
    lines = ["# PolyScout research report", "", safe_text(question), "",
             f"Run status: {status}. Source access is an observation at capture time, not a guarantee of present accuracy.", "",
             "## Findings", ""]
    if not result.claims:
        lines.append("Insufficient evidence — no supported conclusion can be reported (confidence: low).")
    for claim in result.claims:
        citations = " ".join(f"[{key}](#{key.lower()})" for key in claim.evidence_ids)
        lines.extend([f"- {safe_text(claim.text)} {citations} **Confidence: {claim.confidence}.**",
                      f"  Rationale: {safe_text(claim.rationale)}"])
    lines.extend(["", "## Unable to obtain / 未能获取", ""])
    gaps = [f"{e.id}: {e.adapter}, query={e.query}: {e.reason}" for e in records if e.status != "retrieved"]
    gaps.extend(result.gaps)
    gaps.extend(notes)
    lines.extend(["- " + safe_text(gap) for gap in gaps] or ["No retrieval failure was recorded; coverage may still be incomplete."])
    lines.extend(["", "## Evidence", ""])
    for record in records:
        if record.status != "retrieved":
            continue
        lines.extend([
            f"### {record.id}", "", safe_text(record.title), "",
            f"Source: <{str(record.url).replace('>', '%3E').replace('<', '%3C')}>  ",
            f"Adapter: {record.adapter}; credibility: {record.credibility}; kind: {record.excerpt_kind}; captured: {record.retrieved_at.isoformat()}", "",
            "Verbatim excerpt (search snippets are provider text, not verified page quotations):", "",
            *["> " + safe_text(line) for line in record.excerpt.splitlines()], "",
        ])
    lines.extend(["## Requests and limitations", "",
                  f"HTTP attempts by service: {counts}. No automatic retries.",
                  f"LLM usage reported by provider: {tokens}. Monetary cost is not computed; consult your provider.",
                  "Citation IDs and provenance are checked mechanically; semantic entailment and external truth require human review.",
                  "v0.1 covers GitHub repository metadata and search snippets only. Bilibili/ASR, CSDN, deep-page fetching and MCP are not implemented.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
