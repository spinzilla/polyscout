# PolyScout

**Break the walls between content platforms.** A deep-reconnaissance research agent that goes where search indexes can't: Bilibili video subtitles, GitHub API ground truth, and the deep layers of the Chinese web — then delivers every conclusion with verbatim evidence attached.

> Status: 🚧 early design. Spike validated, architecture in progress. Star to follow along.

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
- [ ] Requirements freeze (grilled with the design-tree method)
- [ ] Architecture: adapter interface, evidence store schema, planner
- [ ] v1: GitHub + web search + Bilibili adapters, CLI
- [ ] MCP server
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

> 当前处于早期设计阶段，欢迎 Star 关注。
