"""兼容壳：实现已迁至 app.domains.radar.radar_predict。"""

from __future__ import annotations

import sys

from app.domains.radar import radar_predict as _impl

sys.modules[__name__] = _impl
