# PolyScout v0.2 architecture

Status: implementation contract for the v0.2 Python package. This document describes
bounded behavior, not a claim of live provider acceptance. The frozen baseline is
[REQUIREMENTS.md](REQUIREMENTS.md) (including the 2026-10-05 third-round amendment);
the product hypothesis and its limits are in [SPIKE.md](SPIKE.md).

## Scope and design

The Python library is the core; Typer is a thin CLI. Runtime dependencies are only
httpx, pydantic and typer. JSONL persistence and orchestration use the standard
library. Pytest is a development dependency; setuptools is build tooling only.
There is no hosted service, managed quota, billing or browser automation. The v0.3b
MCP server is a thin stdio entry point exposing only bounded source queries and
adapter declarations; it does not host a web service or research task queue.

```text
CLI / Python caller -> Settings -> planner.research
                                  |  LLM: plan, optionally replan
                                  +-- GitHubAdapter: search -> repository detail
                                  +-- WebSearchAdapter: Tavily POST / Bing-style GET
                                  |  bounded parallel source collection
                                  v
                             EvidenceStore
                                  |  LLM: synthesis -> citation validation
                                  v
                      report.md + evidence.jsonl + raw/ + run.json
```

GitHub discovery is followed by official repository detail requests. This directly
targets the spike's archived-repository failure mode. Search excerpts support
breadth, but do not establish the truth of the linked page. v0.1 does not fetch
deep pages or implement subtitles, ASR or full-license retrieval. Those capabilities
must not be inferred from the broader product positioning.

## Adapter contract

`adapters.base.Adapter` defines `async search(query) -> list[Observation]` around
an adapter's `fetch` implementation. Adapters are instantiated per run; their state
is not shared between research runs. The planner owns sequencing: different
adapters run concurrently, queries inside one adapter run serially.

| Declaration field | Meaning / invariant |
| --- | --- |
| `name` | Stable platform name: `github`, `websearch`, `bilibili` or `csdn` |
| `capabilities` | Explicit supported operations; never advertise unimplemented crawling |
| `compliance.terms_url` | Provider terms reference; not a legal approval certificate |
| `compliance.access_policy` | Allowed channel and operator responsibilities |
| `compliance.robots_policy` | API-only access; no direct target-page crawling |
| `compliance.retention` | Literal `excerpts_and_links_only` |
| `compliance.cookies_supported` | False by default; True only for adapters whose platform keeps core content behind a login soft-wall (v0.2: bilibili). Such adapters accept only operator-supplied cookies (BYO), never bundled ones, and must enforce a per-run cookie-request budget |
| `compliance.wall_action` | Literal `open_circuit_for_run` |

Declarations are serialized to `run.json`. A compatible search endpoint may have
different terms from the protocol vendor: the operator must review those terms.
Provider indexing does not imply robots permission for subsequent direct crawling.
Future page adapters must check robots and terms before accessing target pages;
they may not inherit the v0.1 API-only rationale.

### Hard-wall circuit protocol

States: **ready -> requesting -> ready**, or **requesting -> blocked**; a blocked
adapter never makes another request in that run. Cancellation leads to stopped.

- HTTP 401/403/429, redirects, recognized CAPTCHA/login/risk-control HTML, and JSON
  provider-wall errors create `status=blocked` evidence with a stable reason code.
- Stop the current adapter immediately, including any remaining repository detail
  requests. Subsequent queries return `circuit_open:*` without network access.
- Detour means continue another already configured adapter, not attempt alternate
  credentials, proxies, CAPTCHA solutions or another route to the same wall.
- Timeouts, invalid payloads and other HTTP failures become unavailable records.
  There are zero automatic retries. Three consecutive failed queries stop that
  adapter. Planner rounds and queries are also bounded independently.
- Redirects are never followed, including apparently benign canonicalization.
  This is deliberately conservative; configure the final API endpoint.
- Requests have a 20-second HTTP timeout and a 2 MB response limit. Response bodies
  are transient; error bodies and credential-bearing exception strings are discarded.
- Cancellation propagates through an asyncio TaskGroup, awaits child cleanup, closes
  owned clients and writes a cancelled report/manifest. Completed query batches are
  retained; partially received bodies and unfinished detail batches are not evidence.

### Wire protocols

GitHub: `GET https://api.github.com/search/repositories?q=...&per_page=3`, followed
by at most three `GET /repos/{owner}/{repo}` requests. An optional
`POLYSCOUT_GITHUB_TOKEN` is a bearer token; absent tokens use the public anonymous
API. The client never requests private repositories deliberately, and discards any
detail response marked private. Quotas are provider-controlled; on limit signals
the run records the gap instead of waiting or retrying.

Tavily style: POST the configured search endpoint with bearer authorization,
`query`, `max_results=3`, `include_answer=false`, `include_raw_content=false`;
read `results[].{title,url,content}`.

Bing style: GET a user-configured compatible endpoint with query parameters
`q`, `count=3`, header `Ocp-Apim-Subscription-Key`; read
`webPages.value[].{name,url,snippet}`. This is protocol compatibility, not a promise
that a legacy Microsoft service is still available. No Bing endpoint is assumed.

Bilibili (v0.2): all requests are anonymous except subtitle endpoints when the
operator supplies their own `POLYSCOUT_BILIBILI_SESSDATA` cookie. Flow:
`GET /x/web-interface/nav` (wbi key material, returned even when unauthenticated)
→ wbi-signed `GET /x/web-interface/wbi/search/type?search_type=video&keyword=...`
(wbi signing is the platform's public web-client signature: mixin-key permutation +
md5; computed locally, it is not a risk-control bypass) → per video
`GET /x/web-interface/view?bvid=...` (metadata, anonymous) →
`GET /x/player/v2?bvid=...&cid=...` (subtitle track list; the platform returns an
empty track list to anonymous callers — a soft login wall measured 2026-10-05 on
10/10 probed videos) → subtitle JSON download. Chinese tracks are preferred, then
AI tracks. Subtitle excerpts are verbatim lines capped at 800 characters
(`excerpt_kind=subtitle_excerpt`); videos without obtainable subtitles degrade to
verbatim metadata field excerpts (`api_fields`), never paraphrased content.
Risk-control business codes (-352/-412/-799) are hard walls; other non-zero codes
are ordinary failures. Requests carrying the BYO cookie are hard-capped at 20 per
run; beyond the budget the adapter degrades to anonymous behavior. A browser-class
User-Agent is used because the provider rejects non-browser agents; this is
declared in the adapter's access_policy rather than hidden.

References: [GitHub repository REST API](https://docs.github.com/en/rest/repos/repos#get-a-repository),
[Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search).
Adapters do not claim that documentation review substitutes for live verification.

## Evidence store schema v1.0

Each run gets a new UTC timestamp + random identifier directory. Existing runs are
never reused or overwritten. `evidence.jsonl` contains retrieved observations and
retrieval failures as equally typed records. Pydantic rejects unknown fields.

| Field | Type | Meaning / validation |
| --- | --- | --- |
| `schema_version` | literal `1.0` | Schema evolution marker |
| `id` | `E0001` etc. | Unique within a run; monotonically assigned |
| `adapter` | string | Provenance channel |
| `query` | string, 1..500 chars | Query that produced the observation |
| `status` | retrieved / unavailable / blocked | Failure is a first-class record |
| `url` | HTTP(S) URL or null | Required for retrieved evidence; API detail URL or search target |
| `title` | string <=300 chars | Display label, not an evidentiary assertion |
| `excerpt` | string <=1200 chars | Exact source fragments; empty on failure |
| `excerpt_kind` | api_fields / search_snippet / subtitle_excerpt / none | Prevents snippets masquerading as page quotations; subtitle_excerpt (v0.2) marks verbatim caption lines |
| `credibility` | primary / secondary / unknown | Source provenance, not claim confidence |
| `reason` | string or null | Stable failure code; mandatory on unavailable/blocked records |
| `retrieved_at` | timezone-aware datetime | UTC capture time by default |
| `raw_path` | relative path or null | `raw/E0001.txt`; bounded excerpt only |
| `excerpt_sha256` | hex SHA256 or null | Integrity link to exact UTF-8 excerpt bytes |

GitHub excerpts concatenate separately verbatim JSON field fragments, one per line;
they are not one contiguous original paragraph. Search snippets are an unmodified
prefix of at most 800 characters of provider-supplied text, not verified quotes from
the destination page. `raw/` stores only those excerpts, never HTML pages, full
API payloads, cookies, credentials or full LLM transcripts. Evidence failures have
no raw artifact. `EvidenceStore.read` validates IDs, fixed paths, hashes and content.

`report.md` links claims to evidence IDs, URLs and excerpts. `run.json` records run
status, declarations, per-service HTTP attempt counts and provider-reported LLM
usage. Missing usage is explicitly incomplete; no currency estimate is fabricated.
Configured secrets found in returned source material cause that observation to be
omitted and replaced with a gap. This is not a universal third-party secret scanner.

Files are appended/written synchronously. There is no database, background flush,
resume support, multiprocess writer or transactional guarantee against power loss.

## Planner loop

```text
validate BYOK settings, input and round budget
create a unique run directory; mark running
instantiate per-run adapters and LLM client
for round in 1..max_rounds (default 2, maximum 2):
    ask LLM for subquestions and platform-specific queries
    if initial planning fails: use a disclosed original-question fallback
    if follow-up planning fails: stop planning
    remove duplicate queries; cap at 3 queries per adapter per round
    record platforms omitted by the plan as coverage gaps
    concurrently for each adapter:
        sequentially execute its queries
        on hard wall: open circuit and record blocked observations
    append completed observations with unique IDs and raw excerpt hashes
    if both platforms supplied evidence, or no new queries, or all circuits stop:
        break
ask LLM to synthesize retrieved evidence (skip if none)
reject unknown/unavailable citations; cap confidence
on invalid synthesis: produce an explicitly extractive report
write report and completed/partial manifest; close owned resources
on cancellation/error: retain completed batches, write cancelled/failed artifacts
```

The GitHub query language is kept distinct from web `site:` operators. Subquestions
and query purposes are used in the planning contract; they are not factual report
claims. Historical evidence summaries, used queries and blocked adapters inform a
second plan. No autonomous unbounded exploration or orchestration framework is used.

At most 3 LLM requests, 24 GitHub requests (6 searches + 18 detail requests) and
6 search-provider requests occur under the default budget. Empty/missing sources,
circuits and deduplication lower this ceiling. This can exceed a provider's short
window quota; rate-limit walls are recorded, not bypassed. Token cost depends on
the BYOK endpoint. The implementation sets no hosted budget or billing policy.

The LLM uses `{POLYSCOUT_LLM_BASE_URL}/chat/completions`, configured model and bearer
key. The base normally includes `/v1`; HTTP is allowed only for loopback models.
JSON is requested by schema in the system prompt, then validated locally; no
vendor-specific structured-output extension is required. Sources are untrusted
data, never executable instructions. Prompt injection can still affect semantic
quality; citation validation does not solve that problem.

## Synthesis contract

`Claim` contains `text`, nonempty `evidence_ids`, `confidence` and `rationale`.
Every claim must reference existing retrieved records. Unknown IDs or references
to failures invalidate synthesis; the report then shows an extractive fallback.
The LLM may not manufacture quotations: all displayed quotes come from the store.
Contradictions and missing support belong in `Synthesis.gaps` and the dedicated
"Unable to obtain / 未能获取" report section. Empty evidence yields no factual claims.

Confidence semantics:

| Level | Meaning | v0.1 enforcement |
| --- | --- | --- |
| high | Strong, independently corroborated support | Never assigned automatically in v0.1 |
| medium | Direct primary observation supports a limited inference | Ceiling for GitHub-only cited claims |
| low | Indirect, incomplete or extractive support | All search-snippet and fallback claims |

Primary/secondary source credibility and claim confidence are separate dimensions.
Neither a valid URL nor a primary API proves a broad recommendation. Mechanical
checks establish citation existence, excerpt integrity and retrieval provenance;
human review must assess semantic support and answer quality. Partial reports exit
the CLI successfully because artifacts exist; their status is printed and stored.
Configuration errors exit 2, unexpected failures 1, interruption 130.

## Compliance constitution -> code

| Frozen rule | Enforcement | Offline verification |
| --- | --- | --- |
| Excerpts + links, no mirrors | bounded Observation fields, provider raw-content disabled, excerpt-only store | bounded snippets, raw integrity, no full responses |
| Hard wall = detour | Transport classification, per-run Adapter circuit, no redirects/retries | 401/403/429/302, HTML/JSON walls, detail-wall short circuit |
| No login-state distribution | BYO-only cookies (2026-10-05 amendment): transport strips all outgoing cookies by default; an adapter may send only the exact operator-configured cookie it declared; per-run cookie budget enforced; no transcript persistence | response Set-Cookie is never sent back; default-strip regression tests; bilibili budget tests |
| Respect robots and ToS | per-adapter declarations, API-only scope, provider terms responsibility | declarations persisted; no target-page requests |

Robots/ToS declarations describe the access policy; an offline test cannot certify
legal compliance or current platform authorization. Real provider operation remains
a separate acceptance layer.

## Frozen requirement coverage and release boundaries

| Requirement | v0.1 implementation or explicit future boundary |
| --- | --- |
| Q1 | English-first package/docs with Chinese Quick Start; Chinese content remains accepted |
| Q2 | Library + CLI + minimal stdio MCP; no hosted web service |
| Q3 | Existing Apache-2.0 LICENSE retained and package metadata declares it |
| Q4 | GitHub + search + Bilibili (v0.2) + CSDN best-effort (v0.3a); no Zhihu/WeChat adapter |
| Q5 | Contract and enforcement mapping above, including the amended BYO-cookie rule |
| Q6 | BYOK OpenAI-compatible HTTP; no hosted quota or billing |
| Q7 | Bilibili adapter: official/AI subtitle tracks via BYO cookie, metadata anonymously; ASR (faster-whisper extra) deferred past v0.2 for separate compliance review |
| Q8 | Versioned Pydantic schema + JSONL + excerpt-only raw directory |
| Q9 | Bounded custom planner and parallel adapters, zero orchestration frameworks |
| Q10 | Five frozen cases and offline anonymization/two-judge scoring in evaluation.py; manual major-release gate, no paid CI calls |
| Q11 | CSDN v0.3a and minimal MCP v0.3b; async research/MCP submit-poll and ASR remain separate slices |
| Q12 | Python >=3.11, allowed runtime stack and pytest |
| Q13 | Student/community project, best-effort issues, no SLA; public live CI health dashboard remains a future release/infrastructure task |

## Manual evaluation (Q10)

`polyscout.evaluation.QUESTIONS` fixes T1 STM32 instrument, T2 IoT RTOS, T3 Deep
Research framework, T4 embedded GUI and T5 Chinese-video transcription. Each case
requires two real reports, saved as `T1-A.md`, `T1-B.md`, etc. Do not substitute
mock fixtures for real research quality evaluation.

```powershell
uv run python -m polyscout.evaluation prepare evaluation-input evaluation-batch --seed 42
uv run python -m polyscout.evaluation score evaluation-batch/private-mapping.json judge1.json judge2.json
```

Share only the `blind/` directory with two independent judges from distinct model
families. Their instructions, exact scoring JSON shape and criterion maxima are in
`JUDGE_INSTRUCTIONS.md`. Keep the mapping private until both scores are recorded.
The script does not call any paid endpoint or send messages to judges. It validates
the two score files and reports per-judge mean margin and penetration advantage.
The release gate requires each judge's mean A-B margin >=15, positive mean
penetration margin and A leading on every topic. Text-style identity leaks and
small-sample limitations from SPIKE.md remain; arithmetic is not semantic validation.

## 中文摘要

v0.1 仅实现 GitHub 仓库详情实查与搜索 API 摘要。硬墙按来源熔断；失败、未覆盖与
证据不足都写入报告。raw 只保存摘录，引用编号通过校验不代表结论必然正确。
离线测试验证可描述的代码性质，真实接口与调研质量需独立验收。
