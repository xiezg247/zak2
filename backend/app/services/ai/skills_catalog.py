"""内置 SKILL.md 目录：list/read + 安全解析。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MAX_SKILL_CHARS = 12000

_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def skills_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "skills"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return meta, body
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
        i += 1
    return {}, text


def _first_nonempty_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def resolve_skill_dir(skill_id: str) -> Path:
    return _safe_skill_dir(skill_id)


def _safe_skill_dir(skill_id: str) -> Path:
    if not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"非法 skill id：{skill_id}")
    root = skills_root().resolve()
    skill_dir = (root / skill_id).resolve()
    try:
        skill_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"非法 skill id：{skill_id}") from exc
    return skill_dir


def _load_skill_meta(skill_id: str, text: str) -> dict[str, Any]:
    meta, body = _parse_frontmatter(text)
    return {
        "id": skill_id,
        "name": meta.get("name") or skill_id,
        "description": meta.get("description") or _first_nonempty_line(body),
    }


def list_skills() -> list[dict]:
    root = skills_root()
    if not root.is_dir():
        return []
    skills: list[dict] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        skill_id = entry.name
        if not _SKILL_ID_RE.match(skill_id):
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8")
        meta = _load_skill_meta(skill_id, text)
        meta["runnable"] = (entry / "skill.py").is_file()
        skills.append(meta)
    return sorted(skills, key=lambda s: s["id"])


def read_skill(skill_id: str) -> dict:
    skill_dir = _safe_skill_dir(skill_id)
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"未找到 skill：{skill_id}")
    text = skill_file.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    content = body.strip()
    if len(content) > MAX_SKILL_CHARS:
        content = content[: MAX_SKILL_CHARS - 20] + "…(truncated)"
    return {
        "id": skill_id,
        "name": meta.get("name") or skill_id,
        "description": meta.get("description") or _first_nonempty_line(body),
        "content": content,
    }
