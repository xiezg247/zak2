"""兼容壳：实现已迁至 app.domains.auth.schemas。"""
from app.domains.auth.schemas import LoginRequest, TokenResponse, UserOut

__all__ = ["LoginRequest", "TokenResponse", "UserOut"]
