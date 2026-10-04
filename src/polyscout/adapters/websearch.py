"""Explicit Tavily POST and Bing-style GET protocols; no target-page scraping."""

from urllib.parse import urlsplit

from pydantic import ValidationError

from polyscout.config import endpoint
from polyscout.models import Observation
from polyscout.transport import FetchError, Transport, json_object
from .base import Adapter, Compliance, Declaration


class WebSearchAdapter(Adapter):
    def __init__(self, transport: Transport, provider: str, api_url: str, key: str):
        super().__init__(transport)
        if provider not in {"tavily", "bing"}:
            raise ValueError("Unknown search protocol")
        self.provider, self.api_url, self.key = provider, endpoint(api_url), key
        self.declaration = Declaration(
            name="websearch", capabilities=("search_snippets", provider + "_protocol"),
            compliance=Compliance(
                terms_url=("https://www.tavily.com/terms" if provider == "tavily" else "https://www.microsoft.com/en-us/servicesagreement"),
                access_policy="Operator must verify the selected provider endpoint's terms and rights to returned excerpts.",
                robots_policy="No target pages fetched. Search API provider mediates indexing; this is not robots clearance for crawling.",
            ),
        )

    async def fetch(self, query: str) -> list[Observation]:
        if not self.key:
            return [self.gap(query, "search_key_not_configured")]
        if self.provider == "tavily":
            response = await self.transport.request(
                "websearch", "POST", self.api_url,
                headers={"Authorization": f"Bearer {self.key}"},
                json={"query": query, "max_results": 3, "include_answer": False, "include_raw_content": False},
            )
            items = json_object(response).get("results")
        else:
            response = await self.transport.request(
                "websearch", "GET", self.api_url,
                headers={"Ocp-Apim-Subscription-Key": self.key}, params={"q": query, "count": 3},
            )
            pages = json_object(response).get("webPages", {})
            items = pages.get("value", []) if isinstance(pages, dict) else None
        if not isinstance(items, list):
            raise FetchError("invalid_search_results")
        records = []
        for item in items[:3]:
            try:
                if not isinstance(item, dict):
                    raise ValueError("invalid item")
                url = item.get("url", "")
                parts = urlsplit(url)
                if parts.scheme not in {"https", "http"} or parts.username or parts.password:
                    raise ValueError("invalid URL")
                content = item.get("content" if self.provider == "tavily" else "snippet")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("missing excerpt")
                records.append(Observation(
                    adapter="websearch", query=query, status="retrieved", url=url,
                    title=str(item.get("title", item.get("name", "")))[:300],
                    excerpt=content[:800], excerpt_kind="search_snippet", credibility="secondary",
                ))
            except (ValidationError, ValueError, TypeError):
                records.append(self.gap(query, "invalid_search_item"))
        return records
