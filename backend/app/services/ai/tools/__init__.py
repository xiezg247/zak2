"""ai_tools 拆分子包：只读 / 技能 / 写工具 + 公共工具。"""

from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
    summarize_write_tool,
)

__all__ = [
    "MAX_RESULT_CHARS",
    "READ_DEFINITIONS",
    "READ_HANDLERS",
    "SKILL_DEFINITIONS",
    "SKILL_HANDLERS",
    "ToolHandler",
    "WRITE_DEFINITIONS",
    "WRITE_HANDLERS",
    "WRITE_TOOL_NAMES",
    "_parse_args",
    "_truncate",
    "summarize_write_tool",
]
