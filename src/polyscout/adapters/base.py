"""Adapter capability and compliance declarations are executable contracts."""

from abc import ABC, abstractmethod
from typing import Literal

from polyscout.models import Model, Observation
from polyscout.transport import FetchError, Transport


class Compliance(Model):
    terms_url: str
    access_policy: str
    robots_policy: str
    retention: Literal["excerpts_and_links_only"] = "excerpts_and_links_only"
    cookies_supported: Literal[False] = False
    wall_action: Literal["open_circuit_for_run"] = "open_circuit_for_run"


class Declaration(Model):
    name: str
    capabilities: tuple[str, ...]
    compliance: Compliance


class Adapter(ABC):
    declaration: Declaration

    def __init__(self, transport: Transport):
        self.transport = transport
        self.wall_reason: str | None = None
        self.failures = 0

    def gap(self, query: str, reason: str, *, blocked: bool = False) -> Observation:
        return Observation(adapter=self.declaration.name, query=query,
                           status="blocked" if blocked else "unavailable", reason=reason)

    async def search(self, query: str) -> list[Observation]:
        if self.wall_reason:
            return [self.gap(query, "circuit_open:" + self.wall_reason, blocked=True)]
        if self.failures >= 3:
            return [self.gap(query, "consecutive_failure_limit")]
        try:
            records = await self.fetch(query)
        except FetchError as exc:
            self.failures += 1
            if exc.wall:
                self.wall_reason = exc.reason
            return [self.gap(query, exc.reason, blocked=exc.wall)]
        if records and not any(record.status == "retrieved" for record in records):
            self.failures += 1
        else:
            self.failures = 0
        return records or [self.gap(query, "no_results")]

    @abstractmethod
    async def fetch(self, query: str) -> list[Observation]:
        """Implement bounded retrieval; never bypass a wall or retain full content."""
        raise NotImplementedError
