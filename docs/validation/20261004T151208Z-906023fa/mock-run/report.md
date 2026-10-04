# PolyScout research report

Which RTOS?

Run status: completed. Source access is an observation at capture time, not a guarantee of present accuracy.

## Findings

- The repository is archived\. [E0001](#e0001) **Confidence: medium.**
  Rationale: API field \[v0\.1 cap: primary API evidence &lt;= medium; search snippets &lt;= low\.\]
- Search describes maintenance concerns\. [E0002](#e0002) **Confidence: low.**
  Rationale: Search result \[v0\.1 cap: primary API evidence &lt;= medium; search snippets &lt;= low\.\]

## Unable to obtain / 未能获取

No retrieval failure was recorded; coverage may still be incomplete.

## Evidence

### E0001

o/repo

Source: <https://api.github.com/repos/o/repo>  
Adapter: github; credibility: primary; kind: api_fields; captured: 2026-10-04T15:12:09.489742+00:00

Verbatim excerpt (search snippets are provider text, not verified page quotations):

> "full\_name":"o/repo"
> "archived":true

### E0002

Context

Source: <https://example.com/>  
Adapter: websearch; credibility: secondary; kind: search_snippet; captured: 2026-10-04T15:12:09.489742+00:00

Verbatim excerpt (search snippets are provider text, not verified page quotations):

> Maintenance concerns\.

## Requests and limitations

HTTP attempts by service: {'llm': 2, 'github': 2, 'websearch': 1}. No automatic retries.
LLM usage reported by provider: {'reported_total_tokens': 84, 'complete': True}. Monetary cost is not computed; consult your provider.
Citation IDs and provenance are checked mechanically; semantic entailment and external truth require human review.
v0.1 covers GitHub repository metadata and search snippets only. Bilibili/ASR, CSDN, deep-page fetching and MCP are not implemented.
