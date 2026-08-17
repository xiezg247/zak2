from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "change-me-in-production-min-32-chars!!"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://zak2:zak2@localhost:5432/zak2"
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_expire_days: int = 7
    login_max_failures: int = 5
    login_lock_window_seconds: int = 900
    redis_url: str = "redis://127.0.0.1:6379/0"
    arq_queue_name: str = "zak2:arq"
    arq_backtest_queue_name: str = "zak2:arq:backtest"
    backtest_task_timeout_s: int = 120
    backtest_max_workers: int = 4
    backtest_subprocess: bool = False
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
    quote_collector_enabled: bool = True
    quote_collect_interval_sec: int = 30
    quote_provider: str = "tickflow"
    tickflow_api_key: str = ""

    @model_validator(mode="after")
    def _validate_production_secret(self) -> Settings:
        if self.environment == "production" and self.jwt_secret == _DEFAULT_JWT_SECRET:
            raise ValueError("生产环境必须设置 JWT_SECRET，禁止使用默认值")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def scheduler_effective_enabled(self) -> bool:
        return bool(self.embedded_scheduler_enabled and self.bars_scheduler_enabled)


@lru_cache
def get_settings() -> Settings:
    return Settings()
