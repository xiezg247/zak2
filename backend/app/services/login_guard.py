"""兼容壳：实现已迁至 app.domains.auth.login_guard。"""
from app.domains.auth.login_guard import *  # noqa: F403
from app.domains.auth.login_guard import is_locked, record_failure, reset

__all__ = ["is_locked", "record_failure", "reset"]
