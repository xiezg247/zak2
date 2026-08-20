"""兼容壳：路由实现已迁至 app.domains.screener.router。"""

from app.domains.screener.router import router
from app.domains.screener.service import _run_detail

__all__ = ["router", "_run_detail"]
