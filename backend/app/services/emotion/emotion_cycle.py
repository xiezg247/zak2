"""兼容壳：实现已迁至 app.domains.emotion.emotion_cycle。"""

from __future__ import annotations

import sys

from app.domains.emotion import emotion_cycle as _impl

sys.modules[__name__] = _impl
