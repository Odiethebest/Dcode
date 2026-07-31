from dcode_agent.llm import (
    SYSTEM_PROMPT,
    _build_synthesis_messages,
    response_language_for,
)


def test_response_language_tracks_chinese_and_english_questions() -> None:
    assert response_language_for("深度剖析 HybridRetriever 的算法") == "Chinese"
    assert response_language_for("How does HybridRetriever work?") == "English"
    assert response_language_for("HTTPBasicAuth?") == "English"


def test_synthesis_message_makes_the_detected_language_mandatory() -> None:
    messages = _build_synthesis_messages(
        question="HybridRetriever 如何工作？",
        context="retrieved code",
        response_language="Chinese",
    )

    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "Required answer language: Chinese" in messages[1]["content"]
    assert "HybridRetriever 如何工作？" in messages[1]["content"]


def test_system_prompt_uses_frontend_supported_math_delimiters() -> None:
    assert "inline math as `$...$`" in SYSTEM_PROMPT
    assert "display math as `$$...$$`" in SYSTEM_PROMPT
    assert "Do not use `\\(...\\)` or `\\[...\\]`" in SYSTEM_PROMPT
