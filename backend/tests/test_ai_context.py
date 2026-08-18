from app.services.ai.ai_context import SYSTEM_PROMPT, build_context_brief


def test_system_prompt_nonempty() -> None:
    assert "投研" in SYSTEM_PROMPT or "助手" in SYSTEM_PROMPT
    assert callable(build_context_brief)
