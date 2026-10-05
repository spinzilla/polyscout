"""Built-in adapters; no browser automation. Cookies only via explicit BYO declaration."""

from .bilibili import BilibiliAdapter
from .github import GitHubAdapter
from .websearch import WebSearchAdapter

__all__ = ["BilibiliAdapter", "GitHubAdapter", "WebSearchAdapter"]
