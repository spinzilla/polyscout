"""Official GitHub REST search followed by current repository detail GETs."""

import json
import re

from pydantic import ValidationError

from polyscout.models import Observation
from polyscout.transport import FetchError, Transport, json_object
from .base import Adapter, Compliance, Declaration


class GitHubAdapter(Adapter):
    declaration = Declaration(
        name="github", capabilities=("repository_search", "repository_details"),
        compliance=Compliance(
            terms_url="https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
            access_policy="Official public REST API; optional bearer token; no private-content workflow.",
            robots_policy="No HTML crawling; API access and rate-limit policy apply.",
        ),
    )

    def __init__(self, transport: Transport, token: str = ""):
        super().__init__(transport)
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def fetch(self, query: str) -> list[Observation]:
        response = await self.transport.request(
            "github", "GET", "https://api.github.com/search/repositories",
            params={"q": query, "per_page": 3}, headers=self.headers,
        )
        items = json_object(response).get("items")
        if not isinstance(items, list):
            raise FetchError("invalid_repository_search")
        records = []
        for item in items[:3]:
            name = item.get("full_name") if isinstance(item, dict) else None
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
                records.append(self.gap(query, "invalid_repository_name"))
                continue
            url = f"https://api.github.com/repos/{name}"
            try:
                detail = await self.transport.request("github", "GET", url, headers=self.headers)
                payload = json_object(detail)
                if payload.get("private") is True:
                    records.append(self.gap(query, "private_repository_not_supported"))
                    continue
                # Preserve literal JSON field fragments, not a paraphrase of API data.
                excerpts = []
                for field in ("full_name", "archived", "disabled", "stargazers_count", "forks_count", "open_issues_count", "pushed_at", "updated_at"):
                    match = re.search(r'"' + field + r'"\s*:\s*(?:"(?:[^"\\]|\\.)*"|true|false|null|[0-9]+)(?=\s*[,}])', detail.text)
                    if match and field in payload and len(match.group()) <= 200:
                        decoded = json.loads("{" + match.group() + "}")[field]
                        if decoded == payload[field]:
                            excerpts.append(match.group())
                if not excerpts:
                    raise FetchError("missing_repository_fields")
                records.append(Observation(
                    adapter="github", query=query, status="retrieved", url=url,
                    title=name, excerpt="\n".join(excerpts), excerpt_kind="api_fields", credibility="primary",
                ))
            except FetchError as exc:
                records.append(self.gap(query, exc.reason, blocked=exc.wall))
                if exc.wall:
                    self.wall_reason = exc.reason
                    break
            except (ValidationError, ValueError):
                records.append(self.gap(query, "invalid_repository_payload"))
        return records
