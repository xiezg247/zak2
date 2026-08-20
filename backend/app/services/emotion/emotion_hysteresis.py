"""兼容壳：实现已迁至 app.domains.emotion.emotion_hysteresis。"""

from __future__ import annotations

import sys

from app.domains.emotion import emotion_hysteresis as _impl

sys.modules[__name__] = _impl
