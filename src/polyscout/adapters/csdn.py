"""CSDN best-effort adapter: anonymous search plus bounded article excerpts.

Live probe (2026-10-10, anonymous GET, browser UA, <=10 requests, >=2s apart):
- ``https://www.csdn.net/robots.txt`` -> 200 text/plain; rules listed
  ``/scripts``, ``/public``, ``/css/``, ``/images/``, ``/content/``, ``/ui/``,
  ``/js/``, ``/article_preview.html*``, ``/tag/``, ``/link/``, ``/tags/``,
  ``/news/``, ``/xuexi/`` and ``/*?*``.
- ``https://so.csdn.net/so/search?q=python`` -> 200 HTML, 6012 bytes, a
  client-side shell with no article links in the returned body.
- A candidate article URL -> 404 HTML. A second identical search probe also
  returned the 6012-byte shell. No article body was retained.
These observations are evidence of current availability only, not a promise of
provider acceptance. Hard walls are recorded and never bypassed.
"""

import re
from html import unescape
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from polyscout.models import Observation
from polyscout.transport import FetchError, Transport
from .base import Adapter, Compliance, Declaration


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_ARTICLE_RE = re.compile(r"https?://blog\.csdn\.net/[A-Za-z0-9_.-]+/article/details/[0-9]+")
_WALL_RE = re.compile(r"captcha|verify you are human|sign in|log in|登录|验证码|风控", re.I)


def _clean(value: str, limit: int) -> str:
    value = re.sub(r"<[^>]+>", " ", unescape(value))
    return re.sub(r"\s+", " ", value).strip()[:limit]


class CSDNAdapter(Adapter):
    declaration = Declaration(
        name="csdn",
        capabilities=("article_search", "article_excerpts"),
        compliance=Compliance(
            terms_url="https://www.csdn.net/",
            access_policy=("Anonymous direct GET only, browser-class User-Agent, "
                           "bounded search then article extraction. No login state, "
                           "proxy reader, CAPTCHA or risk-control bypass."),
            robots_policy=("Respect https://www.csdn.net/robots.txt. Probe observed "
                           "disallowed paths and a query-string rule; operators must "
                           "recheck before live use."),
            cookies_supported=False,
        ),
    )

    def __init__(self, transport: Transport):
        super().__init__(transport)
        self.headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}

    async def fetch(self, query: str) -> list[Observation]:
        search_url = "https://so.csdn.net/so/search?q=" + quote(query, safe="")
        try:
            response = await self.transport.request("csdn", "GET", search_url, headers=self.headers)
            links = list(dict.fromkeys(_ARTICLE_RE.findall(response.text)))[:3]
            if not links:
                return [self.gap(query, "csdn_search_shell_no_article_links")]
            records: list[Observation] = []
            for link in links:
                try:
                    page = await self.transport.request("csdn", "GET", link, headers=self.headers)
                    if _WALL_RE.search(page.text[:20000]):
                        raise FetchError("csdn_html_hard_wall", wall=True)
                    excerpt = self._article_excerpt(page.text)
                    if not excerpt:
                        records.append(self.gap(query, "csdn_article_excerpt_unavailable"))
                        continue
                    records.append(Observation(adapter="csdn", query=query, status="retrieved",
                                              url=link, title=self._title(page.text),
                                              excerpt=excerpt, excerpt_kind="api_fields",
                                              credibility="secondary"))
                except FetchError as exc:
                    blocked = exc.wall or exc.reason in {"http_521", "http_403", "http_429"}
                    records.append(self.gap(query, exc.reason, blocked=blocked))
                    if blocked:
                        self.wall_reason = exc.reason
                        break
            return records
        except FetchError as exc:
            blocked = exc.wall or exc.reason in {"http_521", "http_403", "http_429"}
            if blocked:
                self.wall_reason = exc.reason
            return [self.gap(query, exc.reason, blocked=blocked)]

    @staticmethod
    def _title(html: str) -> str:
        match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if not match:
            match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return _clean(match.group(1), 300) if match else "CSDN article"

    @staticmethod
    def _article_excerpt(html: str) -> str:
        candidates = []
        for pattern in (r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
                        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)'):
            candidates.extend(m.group(1) for m in re.finditer(pattern, html, re.I | re.S))
        match = re.search(r'<article\b[^>]*>(.*?)</article>', html, re.I | re.S)
        if match:
            candidates.append(match.group(1))
        for candidate in candidates:
            excerpt = _clean(candidate, 800)
            if excerpt:
                return excerpt
        return ""
