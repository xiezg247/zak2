"""数据访问层（repositories）。

与原 app/services/*_repo.py 同源，迁入本目录并去掉 _repo 后缀。
函数式风格：模块级函数，首参 db: Session。

子模块按需导入，避免包级连锁 import 导致循环依赖，例如：

    from app.repositories import watchlist
    from app.repositories.watchlist import resolve_symbol_pair
"""
