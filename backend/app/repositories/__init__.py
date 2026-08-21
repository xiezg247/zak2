"""数据访问层（repositories）。

与原 app/services/*_repo.py 同源，迁入本目录并去掉 _repo 后缀。

OOP 风格：
- ORM 单主键模型继承 `BaseRepository[Model]`，获得通用 CRUD 与分页骨架。
- 复合主键 / 非 ORM 模型独立实现，但统一 `Repo(db, user_id)` 构造约定。
- 纯工具函数（如 `resolve_symbol_pair`）仍以模块级函数导出。

子模块按需导入，避免包级连锁 import 导致循环依赖，例如：

    from app.repositories.chat import ChatRepository
"""
