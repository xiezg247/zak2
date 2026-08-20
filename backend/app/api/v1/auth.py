"""兼容壳：路由实现已迁至 app.domains.auth.router。"""
from app.domains.auth.router import router

__all__ = ["router"]
