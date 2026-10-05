"""Bilibili video search: anonymous wbi-signed search + optional BYO-cookie subtitles.

v0.2 宪法修订（REQUIREMENTS 第三轮，用户 2026-10-05 批准）：
- 搜索与视频元数据：完全匿名，wbi 签名为平台 web 端公开标准签名（本地计算，非风控对抗）
- 字幕：B站对匿名请求一律返回空轨（2026-10-05 探测：10/10 视频含明示字幕者均 0 轨），
  仅当用户自带 SESSDATA（BYO 登录态，不内置/不分发）时可获取
- 带 cookie 请求有 per-run 硬预算，耗尽后降级匿名并留痕，防止账号侧风控敞口无界
"""

import hashlib
import re
import time
from urllib.parse import urlencode

from pydantic import ValidationError

from polyscout.models import Observation
from polyscout.transport import FetchError, Transport
from .base import Adapter, Compliance, Declaration

# wbi 签名重排表：B站 web 端公开算法，社区广泛实现
MIXIN_KEY_ENC_TAB = (46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
                     27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
                     37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
                     22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52)

# 平台官方浏览器 UA：B站风控拒绝非浏览器 UA，此处与真实 web 端保持一致；
# 合规声明见 declaration.access_policy
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# B站业务码：风控校验类 = 硬墙（熔断）；其余非 0 码 = 普通失败
_WALL_CODES = {-352, -412, -799}
_BVID_RE = re.compile(r"^BV1[0-9A-Za-z]{9}$")

# 带 cookie 请求的 per-run 硬预算（防账号侧风控敞口；超出即降级匿名）
COOKIE_BUDGET = 20

# 字幕覆盖率阈值：末条时间戳 ÷ 视频时长低于此值 → 疑似换源残留旧字幕轨
# （2026-10-05 实测：换源视频的陈旧 AI 轨内容与现版本完全无关，覆盖仅 40%）
STALE_COVERAGE = 0.85


def wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    """平台 web 端公开签名：mixin key 重排 + 参数排序拼接 + md5。"""
    raw = img_key + sub_key
    mixin = "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]
    signed = dict(params)
    signed["wts"] = int(time.time())
    query = urlencode(sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + mixin).encode()).hexdigest()
    return signed


def _json(response) -> dict:
    """B站响应自解析：成功响应也携带 message 字段，不可用通用 json_object（会误判为错误）。"""
    try:
        value = response.json()
    except ValueError:
        raise FetchError("invalid_json") from None
    if not isinstance(value, dict):
        raise FetchError("invalid_payload")
    code = value.get("code")
    if code == 0:
        data = value.get("data")
        return data if isinstance(data, dict) else {}
    if code in _WALL_CODES:
        raise FetchError(f"bilibili_risk_control_{-code}", wall=True)
    raise FetchError(f"bilibili_error_{-(code or 999999)}")


class BilibiliAdapter(Adapter):
    declaration = Declaration(
        name="bilibili",
        capabilities=("video_search", "video_metadata", "subtitle_excerpts"),
        compliance=Compliance(
            terms_url="https://www.bilibili.com/protocal/licence.html",
            access_policy=("Public web APIs. Anonymous wbi-signed search and metadata. "
                           "Subtitles require the operator's own SESSDATA cookie (BYO login state; "
                           "never bundled, never distributed; per-run cookie-request budget enforced). "
                           "Browser-class UA because the provider rejects non-browser agents."),
            robots_policy="API endpoints only; no page crawling, no danmaku, no video/audio streams.",
            cookies_supported=True,  # v0.2 修订：BYO SESSDATA（不内置/不分发）
        ),
    )

    def __init__(self, transport: Transport, sessdata: str = ""):
        super().__init__(transport)
        self.sessdata = sessdata
        self.headers = {"User-Agent": _UA, "Referer": "https://www.bilibili.com"}
        self._wbi_keys: tuple[str, str] | None = None
        self._cookie_used = 0

    def _auth_cookies(self) -> dict | None:
        """返回本次请求应携带的 BYO cookie；未配置或预算耗尽返回 None（降级匿名）。"""
        if not self.sessdata or self._cookie_used >= COOKIE_BUDGET:
            return None
        self._cookie_used += 1
        return {"SESSDATA": self.sessdata}

    async def _wbi(self) -> tuple[str, str]:
        if self._wbi_keys is None:
            response = await self.transport.request(
                "bilibili", "GET", "https://api.bilibili.com/x/web-interface/nav",
                headers=self.headers)
            # nav 匿名返回 code=-101（未登录）但 wbi_img 照常下发：只认数据，不走路由错误码
            try:
                payload = response.json()
            except ValueError:
                raise FetchError("invalid_json") from None
            wbi = (payload.get("data") or {}).get("wbi_img") or {} if isinstance(payload, dict) else {}
            img = str(wbi.get("img_url", "")).rsplit("/", 1)[-1].split(".")[0]
            sub = str(wbi.get("sub_url", "")).rsplit("/", 1)[-1].split(".")[0]
            if not img or not sub:
                raise FetchError("bilibili_wbi_key_missing")
            self._wbi_keys = (img, sub)
        return self._wbi_keys

    async def fetch(self, query: str) -> list[Observation]:
        img, sub = await self._wbi()
        params = wbi_sign({"search_type": "video", "keyword": query, "page": 1, "page_size": 3},
                          img, sub)
        response = await self.transport.request(
            "bilibili", "GET", "https://api.bilibili.com/x/web-interface/wbi/search/type",
            params=params, headers=self.headers)
        results = _json(response).get("result")
        if not isinstance(results, list):
            raise FetchError("bilibili_invalid_search_payload")
        records: list[Observation] = []
        for item in results[:3]:
            bvid = item.get("bvid") if isinstance(item, dict) else None
            if not isinstance(bvid, str) or not _BVID_RE.match(bvid):
                records.append(self.gap(query, "bilibili_invalid_bvid"))
                continue
            try:
                records.append(await self._video(query, bvid))
            except FetchError as exc:
                records.append(self.gap(query, exc.reason, blocked=exc.wall))
                if exc.wall:
                    self.wall_reason = exc.reason
                    break
        return records

    async def _video(self, query: str, bvid: str) -> Observation:
        """单视频：view 元数据（匿名）→ 字幕轨（BYO cookie）→ 字幕摘录或元数据摘录。"""
        url = f"https://www.bilibili.com/video/{bvid}"
        response = await self.transport.request(
            "bilibili", "GET", "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid}, headers=self.headers)
        info = _json(response)
        cid, title = info.get("cid"), info.get("title")
        if not isinstance(cid, int) or not isinstance(title, str) or not title.strip():
            raise FetchError("bilibili_invalid_video_payload")
        title = title.strip()[:300]

        excerpt = await self._subtitle(bvid, cid, info.get("duration"))
        if excerpt:
            return Observation(adapter="bilibili", query=query, status="retrieved", url=url,
                               title=title, excerpt=excerpt, excerpt_kind="subtitle_excerpt",
                               credibility="secondary")
        # 字幕不可得（无轨/匿名/预算耗尽）→ 降级为逐字元数据字段摘录，不伪装成内容证据
        fields = []
        for field in ("title", "duration", "pubdate", "desc"):
            value = info.get(field)
            if isinstance(value, (str, int)):
                text = str(value).replace("\n", " ").strip()[:200]
                if text:
                    fields.append(f'"{field}": "{text}"' if isinstance(value, str) else f'"{field}": {value}')
        owner = info.get("owner")
        if isinstance(owner, dict) and isinstance(owner.get("name"), str):
            fields.append(f'"owner.name": "{owner["name"].strip()[:100]}"')
        if not fields:
            raise FetchError("bilibili_missing_metadata_fields")
        return Observation(adapter="bilibili", query=query, status="retrieved", url=url,
                           title=title, excerpt="\n".join(fields)[:1200],
                           excerpt_kind="api_fields", credibility="secondary")

    async def _subtitle(self, bvid: str, cid: int, duration) -> str:
        """返回逐字字幕摘录（provenance 头部 + ≤800 字符正文）；不可得返回空串。匿名下平台恒返回空轨。

        头部记录 轨 lan / 来源（uploader|ai）/ 认证方式 / 覆盖率；覆盖率 < STALE_COVERAGE
        追加 STALE-SUSPECT 警告——换源视频的旧字幕轨内容可能完全不属于当前视频。
        """
        cookies = self._auth_cookies()
        response = await self.transport.request(
            "bilibili", "GET", "https://api.bilibili.com/x/player/v2",
            params={"bvid": bvid, "cid": cid}, headers=self.headers,
            cookies=cookies)
        try:
            tracks = (_json(response).get("subtitle") or {}).get("subtitles")
        except FetchError as exc:
            # cookie 失效/未登录 → 该视频降级元数据摘录，不作为整条失败
            if exc.reason == "bilibili_error_101" and not exc.wall:
                return ""
            raise
        if not isinstance(tracks, list) or not tracks:
            return ""
        # 选轨：UP主上传中文字幕 > 其它上传轨 > AI 中文轨 > 其它 AI 轨
        # （AI 轨 lan 带 ai 前缀，如 ai-zh；换源残留的几乎都是 AI 轨）
        def rank(track):
            lan = str(track.get("lan", ""))
            ai = lan.startswith("ai")
            zh = "zh" in lan
            return (0 if (zh and not ai) else 1 if not ai else 2 if zh else 3)
        track = sorted(tracks, key=rank)[0]
        lan = str(track.get("lan", ""))[:20]
        source = "ai" if lan.startswith("ai") else "uploader"
        sub_url = str(track.get("subtitle_url", ""))
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        if not sub_url.startswith("https://"):
            return ""
        response = await self.transport.request(
            "bilibili", "GET", sub_url, headers=self.headers, cookies=self._auth_cookies())
        # 字幕文件格式独立：顶层无 code 字段，body 列表存在即成功
        try:
            body = response.json().get("body")
        except (ValueError, AttributeError):
            return ""
        if not isinstance(body, list):
            return ""
        lines: list[str] = []
        total = 0
        last_end = 0.0
        for entry in body:
            if not isinstance(entry, dict):
                continue
            try:
                last_end = max(last_end, float(entry.get("to") or 0))
            except (TypeError, ValueError):
                pass
            content = entry.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            line = content.strip()
            if total + len(line) > 800:
                break
            lines.append(line)
            total += len(line)
        if not lines:
            return ""
        auth = "cookie" if cookies else "anonymous"
        header = f"[subtitle: {lan} | {source} | auth={auth}"
        coverage = None
        if isinstance(duration, (int, float)) and duration > 0 and last_end > 0:
            coverage = min(last_end / duration, 9.99)
            header += f" | coverage={coverage:.0%}"
        header += "]"
        if coverage is not None and coverage < STALE_COVERAGE:
            header += (f"\n[STALE-SUSPECT: 字幕仅覆盖视频 {coverage:.0%}，疑似换源残留旧轨，"
                       "内容未必属于当前视频——引用前必须复核]")
        return header + "\n" + "\n".join(lines)
