"""兼容壳：实现已迁至 app.domains.emotion.emotion_cycle_cache。"""

from __future__ import annotations

import sys

from app.domains.emotion import emotion_cycle_cache as _impl

sys.modules[__name__] = _impl
