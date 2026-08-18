import pytest

from app.services.ai import skills_catalog
from app.services.ai.skills_catalog import MAX_SKILL_CHARS, list_skills, read_skill


def test_list_includes_positions() -> None:
    ids = {s["id"] for s in list_skills()}
    assert ids == {
        "watchlist",
        "market-emotion",
        "screener",
        "radar",
        "notes",
        "positions",
    }


def test_read_watchlist() -> None:
    doc = read_skill("watchlist")
    assert doc["id"] == "watchlist"
    assert doc["name"] == "watchlist"
    assert doc["description"] == "自选查看与加减；写操作须用户确认"
    assert "get_watchlist" in doc["content"]


def test_read_skill_truncates_oversized_content(tmp_path, monkeypatch) -> None:
    skill_dir = tmp_path / "big-skill"
    skill_dir.mkdir()
    body = "x" * (MAX_SKILL_CHARS + 500)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Big Skill\ndescription: Oversized body\n---\n" + body,
        encoding="utf-8",
    )
    monkeypatch.setattr(skills_catalog, "skills_root", lambda: tmp_path)

    doc = read_skill("big-skill")

    assert doc["name"] == "Big Skill"
    assert doc["description"] == "Oversized body"
    assert doc["content"].endswith("…(truncated)")
    assert len(doc["content"]) <= MAX_SKILL_CHARS


def test_reject_traversal() -> None:
    with pytest.raises(ValueError):
        read_skill("../secrets")
    with pytest.raises(ValueError):
        read_skill("nope")


def test_runnable_flags() -> None:
    m = {s["id"]: s for s in list_skills()}
    assert m["watchlist"]["runnable"] is True
    assert m["screener"]["runnable"] is True
    assert m["radar"]["runnable"] is True
    assert m["market-emotion"]["runnable"] is True
    assert m["notes"]["runnable"] is True
    assert m["positions"]["runnable"] is True
