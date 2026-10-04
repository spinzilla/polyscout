"""BYOK configuration; credentials are never serialized to run artifacts."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def endpoint(value: str) -> str:
    parts = urlsplit(value)
    if (not parts.hostname or parts.username or parts.password or parts.query
            or parts.fragment or any(c.isspace() for c in value)):
        raise ValueError("Endpoints must have a host and no credentials, query or fragment")
    if parts.scheme != "https" and not (
        parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Use HTTPS, or HTTP on loopback for a local model")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = ""
    llm_temperature: float | None = None  # None = 不发送该字段（部分端点拒绝自定义温度）
    llm_timeout: float = 180.0  # 推理模型常需 60s+；适配器超时保持 20s 不变
    search_provider: str = "tavily"
    search_endpoint: str = "https://api.tavily.com/search"
    search_api_key: str = field(default="", repr=False)
    github_token: str = field(default="", repr=False)

    def __post_init__(self):
        if not self.llm_base_url or not self.llm_model:
            raise ValueError("Set POLYSCOUT_LLM_BASE_URL and POLYSCOUT_LLM_MODEL")
        endpoint(self.llm_base_url)
        if not self.llm_api_key and urlsplit(self.llm_base_url).hostname not in {
            "localhost", "127.0.0.1", "::1"
        }:
            raise ValueError("Set POLYSCOUT_LLM_API_KEY (optional only for loopback models)")
        if self.search_provider not in {"tavily", "bing"}:
            raise ValueError("POLYSCOUT_SEARCH_PROVIDER must be tavily or bing")
        if self.search_provider == "bing" and self.search_endpoint == "https://api.tavily.com/search":
            raise ValueError("Set POLYSCOUT_SEARCH_ENDPOINT for the Bing-compatible provider")
        endpoint(self.search_endpoint)

    @property
    def secrets(self) -> tuple[str, ...]:
        return tuple(s for s in (self.llm_api_key, self.search_api_key, self.github_token) if s)

    @classmethod
    def from_env(cls):
        kwargs = {
            name: os.getenv(env, default) for name, env, default in (
                ("llm_base_url", "POLYSCOUT_LLM_BASE_URL", ""),
                ("llm_api_key", "POLYSCOUT_LLM_API_KEY", ""),
                ("llm_model", "POLYSCOUT_LLM_MODEL", ""),
                ("search_provider", "POLYSCOUT_SEARCH_PROVIDER", "tavily"),
                ("search_endpoint", "POLYSCOUT_SEARCH_ENDPOINT", "https://api.tavily.com/search"),
                ("search_api_key", "POLYSCOUT_SEARCH_API_KEY", ""),
                ("github_token", "POLYSCOUT_GITHUB_TOKEN", ""),
            )
        }
        # 温度缺省为 None = 请求中不携带该字段；部分端点（如 kimi-k3）拒绝自定义温度
        temp = os.getenv("POLYSCOUT_LLM_TEMPERATURE", "").strip()
        kwargs["llm_temperature"] = float(temp) if temp else None
        timeout = os.getenv("POLYSCOUT_LLM_TIMEOUT", "").strip()
        if timeout:
            kwargs["llm_timeout"] = float(timeout)
        return cls(**kwargs)
