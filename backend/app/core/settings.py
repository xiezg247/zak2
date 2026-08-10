from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://zak:zak@localhost:5432/zak"
    jwt_secret: str = "change-me-in-production-min-32-chars!!"
    jwt_expire_days: int = 7
    redis_url: str = "redis://127.0.0.1:6379/0"
    tushare_token: str = ""
    bilibili_cookies: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.7
    bars_scheduler_enabled: bool = True
    embedded_scheduler_enabled: bool = True
    scheduler_lock_ttl_seconds: int = 1800
    scheduler_screen_user_id: str = ""
    mcp_enabled: bool = False
    mcp_url: str = ""
    mcp_api_key: str = ""
    mcp_tool_allowlist: str = ""
    # 废弃：stdio 命令；保留字段以免旧 .env 报错，运行时忽略
    mcp_command: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def scheduler_effective_enabled(self) -> bool:
        return bool(self.embedded_scheduler_enabled and self.bars_scheduler_enabled)


@lru_cache
def get_settings() -> Settings:
    return Settings()
