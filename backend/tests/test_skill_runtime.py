from __future__ import annotations

from unittest.mock import MagicMock

from app.services import skill_runtime as rt
from app.services.skill_runtime import SkillContext


def _ctx() -> SkillContext:
    return SkillContext(db=MagicMock(), user_id="u1")


def test_missing_skill_returns_error(tmp_path, monkeypatch) -> None:
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    out = rt.run_skill_module("nope", _ctx(), {})
    assert "error" in out


def test_run_success(tmp_path, monkeypatch) -> None:
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    d = tmp_path / "demo"
    d.mkdir()
    (d / "skill.py").write_text(
        "def run(ctx, args):\n    return {'ok': True, 'uid': ctx.user_id, 'n': args.get('n')}\n",
        encoding="utf-8",
    )
    out = rt.run_skill_module("demo", _ctx(), {"n": 3})
    assert out == {"ok": True, "uid": "u1", "n": 3}


def test_timeout_returns_error(tmp_path, monkeypatch) -> None:
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    monkeypatch.setattr(rt, "SKILL_TIMEOUT_SEC", 0.2)
    d = tmp_path / "slow"
    d.mkdir()
    (d / "skill.py").write_text(
        "import time\ndef run(ctx, args):\n    time.sleep(2)\n    return {}\n",
        encoding="utf-8",
    )
    out = rt.run_skill_module("slow", _ctx(), {})
    assert "error" in out
    assert "超时" in str(out["error"]) or "timeout" in str(out["error"]).lower()


def test_illegal_id() -> None:
    out = rt.run_skill_module("../x", _ctx(), {})
    assert "error" in out
