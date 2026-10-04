"""Built-in adapters; no browser automation or cookie injection."""

from .github import GitHubAdapter
from .websearch import WebSearchAdapter

__all__ = ["GitHubAdapter", "WebSearchAdapter"]
