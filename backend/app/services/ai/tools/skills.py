"""内置投研技能工具（ai_tools 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ai.tools._common import ToolHandler


def _list_skills(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = db, user_id, args
    from app.services.ai import skills_catalog

    return {"skills": skills_catalog.list_skills()}


def _read_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = db, user_id
    from app.services.ai import skills_catalog

    sid = str(args.get("skill_id") or "").strip()
    try:
        return skills_catalog.read_skill(sid)
    except ValueError as exc:
        return {"error": str(exc)}


def _run_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai.skill_runtime import SkillContext, run_skill_module

    sid = str(args.get("skill_id") or "").strip()
    if not sid:
        return {"error": "缺少 skill_id"}
    payload = {k: v for k, v in args.items() if k != "skill_id"}
    return run_skill_module(sid, SkillContext(db=db, user_id=user_id), payload)


SKILL_HANDLERS: dict[str, ToolHandler] = {
    "list_skills": _list_skills,
    "read_skill": _read_skill,
    "run_skill": _run_skill,
}

SKILL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "列出内置投研 Skill 目录（id、名称、简介），按需再 read_skill 加载全文",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "读取指定 skill 的 SKILL.md 全文（只读）",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "如 watchlist、radar"},
                },
                "required": ["skill_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill",
            "description": "执行内置 skill 目录下 skill.py 的 run()（只读示范；超时约 5s）",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "如 market-emotion"},
                },
                "required": ["skill_id"],
                "additionalProperties": True,
            },
        },
    },
]
