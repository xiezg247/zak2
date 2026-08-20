"""兼容壳：实现已迁至 app.domains.emotion.emotion_thresholds。"""

from __future__ import annotations

import sys

from app.domains.emotion import emotion_thresholds as _impl

sys.modules[__name__] = _impl
