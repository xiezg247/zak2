"""行情采集进程入口：uv run python -m app.quote_collector"""

from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    from app.services.quote_collect.loop import run_forever

    run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
