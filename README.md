# PolyScout

**Break the walls between content platforms.** A deep-reconnaissance research agent that goes where search indexes can't: Bilibili video subtitles, GitHub API ground truth, and the deep layers of the Chinese web — then delivers every conclusion with verbatim evidence attached.

> Status: v0.2 implementation — GitHub repository metadata + search APIs + Bilibili video metadata/subtitles (subtitles require your own login cookie), with evidence reports. Offline acceptance evidence is in `docs/validation/`; live provider behavior is not yet verified. CSDN and MCP remain future work.

[中文说明](#中文说明)

---

## Why

Every deep-research product on the market — OpenAI/Gemini/Perplexity Deep Research, Kimi, Metaso — reads from the same pool: **search-engine-indexable web pages**. But some of the most valuable technical knowledge lives outside that pool:

- 🎬 **Bilibili** — hours of dense engineering tutorials locked inside videos (invisible to search)
- 🐙 **GitHub** — repos whose *actual* maintenance state contradicts their marketing (an archived repo was still being recommended as "enterprise-grade" two days after archival — our spike caught this, commercial products didn't)
- 🧱 **Walled gardens** — Zhihu, WeChat official accounts, CSDN deep content

We ran a blind spike to prove this matters: 3 cross-platform research questions, our multi-platform recon process vs. a leading free commercial deep-research product, scored blind by **two independent judge models from different families** (deepseek-v4-pro, gpt-6-astra). **Our process won all 3 rounds under both judges, by an average margin of ~+38 points /100** — decisively on the "unique source penetration" dimension. Full methodology: [docs/SPIKE.md](docs/SPIKE.md).

## What it is

A Python package (CLI + MCP server) that turns a research question into an **evidence-graded report**:

```
question → planner → source router (per-platform adapters)
        → extraction ladder (API → embedded JSON → web → CDP)
        → evidence store (verbatim quote | URL | credibility tier | timestamp)
        → synthesis (every claim pinned to evidence)
```

**v1 source classes:**
| Source | Channel | Notes |
|---|---|---|
| Web search | Tavily / Bing / compatible APIs | baseline |
| GitHub | official REST API | ground-truth repo stats |
| Bilibili | subtitle / ASR transcription | flagship differentiator |
| CSDN | best-effort | adapter interface open for community |

Zhihu / WeChat official accounts are **explicitly out of v1 scope** (hard walls + compliance); the adapter interface leaves room for the community.

## Compliance constitution (non-negotiable)

This project is **not a scraper**. Four rules are architectural constraints, enforced in the adapter contract:

1. **Excerpts + links only.** No content mirrors, ever.
2. **Hard wall = detour.** CAPTCHAs, risk-control pages and login walls are never bypassed or cracked — the adapter switches to alternative sources and logs the wall honestly.
3. **No login-state distribution.** No cookie injection in v1.
4. **robots.txt and platform ToS respected.** Every adapter ships an embedded compliance declaration.

## LLM access

**BYOK only** — bring your own OpenAI-compatible endpoint (official, DeepSeek, relay, or local vLLM). No hosted quota, no billing, no lock-in.

## Roadmap

- [x] Blind spike: differentiation validated (2 judge families, 3/3 wins)
- [x] Requirements freeze (grilled with the design-tree method)
- [x] Architecture: adapter interface, evidence store schema, planner
- [x] v0.1: GitHub + web search adapters, CLI, evidence store
- [x] v0.2: Bilibili adapter (anonymous search/metadata + BYO-cookie subtitles)
- [ ] v0.3: CSDN adapter + MCP server
- [ ] Community adapter program + CI health probes

## License

Apache-2.0 — patent grant included, enterprise-friendly.

---

## 中文说明

**打破平台之间的信息壁垒。** 一个深潜侦察型调研 agent：去搜索引擎索引够不到的地方（B站视频字幕、GitHub API 实查、中文互联网深层内容），并且让每条结论都挂上逐字证据。

### 为什么做

市面上所有深度研究产品读的都是同一个池子：**搜索引擎能索引的网页**。但中文互联网最有价值的技术内容大量锁在池子外——B站教程视频、知乎长答、公众号深度文。我们做过双盲对照实验：3 道跨平台调研题，我方多平台穿透流程 vs 头部免费商业深度研究产品，两个不同家族的独立评委模型盲评——**我方三题全胜，平均领先约 38 分（满分 100）**，胜负手正是「独有信源穿透」维度。实验方法与数据见 [docs/SPIKE.md](docs/SPIKE.md)。

### 合规宪法（不可谈判）

本项目**不是爬虫工具**，四条规则是架构级约束：①只输出摘录+链接，永不建内容镜像；②硬墙即绕，永不破解验证码/风控/登录墙；③不分发登录态；④尊重 robots 与平台条款，每个 adapter 内嵌合规声明。

### LLM 接入

纯 BYOK（自带 OpenAI 兼容端点 key），无托管、无计费、无锁定。

> 当前为 v0.2 实现：GitHub 实查、搜索 API、B站视频元数据/字幕（字幕需自带登录 cookie）、证据报告；尚未经真实环境验证。CSDN 与 MCP 留待后续版本。

## Quick Start

Python 3.11+ is required. From this checkout, use uv to create a local environment.
All setup/test cache and temporary files can stay inside the project:

```powershell
New-Item -ItemType Directory -Force .cache/uv,.cache/pip,.tmp | Out-Null
$env:UV_CACHE_DIR = Join-Path $PWD '.cache/uv'
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
$env:TMP = Join-Path $PWD '.tmp'
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
$env:PYTEST_DEBUG_TEMPROOT = $env:TMP
$env:UV_PYTHON_DOWNLOADS = 'never'
uv sync
uv run polyscout --help
uv run polyscout research --help
```

With an existing virtual environment, `python -m pip install .` installs the same
library and `polyscout` entry point. Runtime dependencies are httpx, pydantic and
typer; pytest is development-only, setuptools is build-only. No system install is
needed. `uv.lock` pins the development environment.

Set your own OpenAI-compatible model endpoint, then your search provider. Replace
the example values locally; do not put real keys in source files or reports.

```powershell
$env:POLYSCOUT_LLM_BASE_URL = 'https://your-provider.example/v1'
$env:POLYSCOUT_LLM_API_KEY = '<your-key>'
$env:POLYSCOUT_LLM_MODEL = '<your-model>'
$env:POLYSCOUT_SEARCH_PROVIDER = 'tavily'
$env:POLYSCOUT_SEARCH_ENDPOINT = 'https://api.tavily.com/search'
$env:POLYSCOUT_SEARCH_API_KEY = '<your-search-key>'
# Optional: your own Bilibili login cookie enables subtitle excerpts (BYO, never distributed).
# Without it the Bilibili adapter still returns anonymous video search and metadata.
$env:POLYSCOUT_BILIBILI_SESSDATA = '<your-own-sessdata>'
# Optional: otherwise GitHub uses the anonymous public REST API.
# $env:POLYSCOUT_GITHUB_TOKEN = '<optional-token>'
uv run polyscout research "Compare maintenance of open-source RTOS projects" --output runs
```

This command makes BYOK network requests and may incur your providers' charges.
It is not an offline demo. No hosted quota or billing is provided. For a local
OpenAI-compatible model, a loopback HTTP URL is supported and the LLM key may be
empty. The base URL must include the provider's API prefix (usually `/v1`), not
`/chat/completions`.

For a Bing-style compatible API, set `POLYSCOUT_SEARCH_PROVIDER=bing` and explicitly
set `POLYSCOUT_SEARCH_ENDPOINT` to your provider's search URL. It uses GET with `q`
and `count`, the `Ocp-Apim-Subscription-Key` header, and the `webPages.value` response
shape. This does not promise availability of any historical Bing endpoint.
Missing search keys yield an explicit retrieval gap while GitHub can continue.

Each invocation creates a fresh `runs/<UTC timestamp>-<random id>/` containing:

- `report.md`: conclusions with evidence links, confidence and retrieval gaps.
- `evidence.jsonl`: typed evidence and failure records.
- `raw/`: bounded verbatim excerpts only, with hashes; no full-page mirror.
- `run.json`: completion status, adapter declarations, HTTP attempt counts and
  provider-reported LLM token usage (marked incomplete when unavailable).

The default maximum is two planning rounds, three queries per adapter per round,
and three results per query. Use `--max-rounds 1` for a smaller request budget.
Hard walls open the adapter circuit for the rest of the run, with no retries or
bypass. Ctrl+C cancels outstanding work and retains completed query batches.
Partial reports are still valid artifacts: inspect their printed/stored status.

Library usage shares the same core:

```python
import asyncio
from polyscout.config import Settings
from polyscout.planner import research

result = asyncio.run(research("Compare RTOS maintenance", Settings.from_env(), "runs"))
print(result.run_dir, result.status)
```

Offline tests (after installing dependencies) make no real provider requests:

```powershell
$env:UV_OFFLINE = 'true'
uv run pytest
```

The tests mock HTTP and block real outbound connections; Windows asyncio's internal
loopback socketpair is permitted solely for event-loop wakeups. They establish
controlled-environment behavior, not live API acceptance or research quality.
For the five-question manual, independently judged release evaluation, see
[ARCHITECTURE.md](docs/ARCHITECTURE.md#manual-evaluation-q10).

### 中文快速开始

需要 Python 3.11+。先按上面的 PowerShell 示例设置项目内缓存与临时目录，再运行
`uv sync`。配置自己的 LLM 地址、模型名、key，以及搜索 API key 后执行：

```powershell
uv run polyscout research "比较开源 RTOS 项目的维护状态" --output runs
```

这个命令会调用你配置的接口，费用由相应服务商收取。GitHub 默认匿名访问，token
可选；搜索 key 未配置时会在报告中标记“未能获取”。结果目录包含证据 JSONL、报告、
有限逐字摘录及请求统计。报告有证据编号不等于结论已被证实：搜索摘要仅为间接证据，
真实接口效果与结论质量仍需人工验收。`uv run pytest` 全部离线，不需要真实 key。

### Maintenance / 维护说明

PolyScout is a student-maintained personal project with community participation.
Issue responses are best-effort; there is no SLA. A public CI adapter-health
dashboard is planned but is not deployed by this v0.1 change. Offline adapter
contract tests are not a live service-health dashboard.

本项目由学生个人维护、社区共同参与；issue 尽力响应，不承诺 SLA。公开 CI 健康看板
尚未部署，不能把离线测试通过当作真实平台健康状态。
