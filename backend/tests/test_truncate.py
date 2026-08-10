from src.tools.truncate import truncate_text


def test_truncate_text_short_unchanged():
    text = "hello world"
    assert truncate_text(text) == text


def test_truncate_text_long_has_marker():
    text = "x" * 5000
    result = truncate_text(text)
    assert result.startswith("x" * 2000)
    assert "truncated" in result
    assert len(result) < len(text)


def test_truncate_text_at_exact_limit_unchanged():
    text = "x" * 2000
    assert truncate_text(text) == text
