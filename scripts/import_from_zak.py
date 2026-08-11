#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.zak_import import import_tables, tables_for_import  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="从 zak PG 一次性导入到 zak2")
    p.add_argument("--force", action="store_true")
    p.add_argument("--with-market-sync-tables", action="store_true")
    args = p.parse_args()
    src = os.environ.get("ZAK_IMPORT_DATABASE_URL") or ""
    dst = os.environ.get("DATABASE_URL") or ""
    if not src or not dst:
        print("需要 ZAK_IMPORT_DATABASE_URL 与 DATABASE_URL", file=sys.stderr)
        return 2
    tables = tables_for_import(with_market_sync=args.with_market_sync_tables)
    counts = import_tables(src, dst, tables, force=args.force)
    for t, n in counts.items():
        if n < 0:
            print(f"{t}: skipped (missing on source or target)")
        else:
            print(f"{t}: {n}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
