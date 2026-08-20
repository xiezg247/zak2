"""兼容壳：实现已迁至 app.domains.auth.repository。"""
from app.domains.auth.repository import UserRepository

__all__ = ["UserRepository"]
