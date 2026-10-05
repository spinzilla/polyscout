"""Bounded requests, no automatic retries, redirects or outgoing cookies."""

from collections import Counter

import httpx


class FetchError(Exception):
    def __init__(self, reason: str, *, wall: bool = False):
        self.reason, self.wall = reason, wall
        super().__init__(reason)


class Transport:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.counts: Counter = Counter()

    async def request(self, service: str, method: str, url: str, timeout: float = 20,
                      cookies: dict | None = None, **kwargs) -> httpx.Response:
        # 适配器保持 20s 紧凑超时（防挂死）；LLM 推理调用由调用方传入更长超时
        self.counts[service] += 1
        request = self.client.build_request(method, url, timeout=timeout, **kwargs)
        request.headers.pop("cookie", None)
        # 默认不外发任何 cookie（宪法默认）；仅当 adapter 显式申请（BYO 登录态，
        # v0.2 修订案，见 REQUIREMENTS 第三轮）时才携带其显式给出的 cookie。
        if cookies:
            request.headers["cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        # A provider may set cookies; no subsequent request may transmit them.
        try:
            response = await self.client.send(request, stream=True, follow_redirects=False)
            try:
                if response.status_code in {401, 403, 429} or 300 <= response.status_code < 400:
                    raise FetchError(f"http_{response.status_code}_wall", wall=True)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise FetchError("response_too_large")
                headers = dict(response.headers)
                headers.pop("content-encoding", None)
                headers.pop("content-length", None)
                result = httpx.Response(response.status_code, headers=headers,
                                        content=bytes(body), request=request)
            finally:
                await response.aclose()
        except httpx.HTTPError:
            # Exception strings may include URLs, tokens or provider response bodies.
            raise FetchError("network_error") from None
        content_type = result.headers.get("content-type", "")
        text = result.text.lower()
        if "html" in content_type or text.lstrip().startswith(("<!doctype html", "<html")):
            if any(marker in text for marker in ("captcha", "sign in", "log in", "risk control", "verify you are human", "验证码", "登录")):
                raise FetchError("html_hard_wall", wall=True)
        if result.is_error:
            raise FetchError(f"http_{result.status_code}")
        return result


def json_object(response: httpx.Response) -> dict:
    try:
        value = response.json()
    except ValueError:
        raise FetchError("invalid_json") from None
    if not isinstance(value, dict):
        raise FetchError("invalid_payload")
    error = value.get("error") or value.get("message")
    if error:
        import json
        text = json.dumps(error, ensure_ascii=False).lower()
        wall = any(w in text for w in ("captcha", "login", "risk", "unauthorized", "rate limit", "requires authentication", "access denied", "验证码", "登录"))
        raise FetchError("provider_wall" if wall else "provider_error", wall=wall)
    return value
