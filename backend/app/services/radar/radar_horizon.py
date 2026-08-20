"""兼容壳：实现已迁至 app.domains.radar.radar_horizon。"""

from __future__ import annotations

import sys

from app.domains.radar import radar_horizon as _impl

sys.modules[__name__] = _impl
