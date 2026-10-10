"""Built-in adapters; no browser automation. Cookies only via explicit BYO declaration."""

from .bilibili import BilibiliAdapter
from .csdn import CSDNAdapter
from .github import GitHubAdapter
from .websearch import WebSearchAdapter

__all__ = ["BilibiliAdapter", "CSDNAdapter", "GitHubAdapter", "WebSearchAdapter"]
