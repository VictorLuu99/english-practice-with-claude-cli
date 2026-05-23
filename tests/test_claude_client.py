import json
from unittest.mock import AsyncMock, patch

import pytest

from english_bot.claude_client import ClaudeClient
from english_bot.models import Feedback, FeedbackParseError


@pytest.fixture
def system_prompt(tmp_path):
    p = tmp_path / "system.md"
    p.write_text("# Test system prompt")
    return p


async def test_generate_prompt_returns_stripped_single_line(system_prompt):
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value="  Hôm nay tôi có `meeting` mới.  \n")):
        result = await client.generate_prompt()
    assert result == "Hôm nay tôi có `meeting` mới."


async def test_evaluate_returns_feedback(system_prompt):
    payload = json.dumps({
        "transcript": "I work here for 3 years",
        "evaluation_text": "🎙️ You said: ...",
        "model_english": "I have been working here for three years.",
        "vi_summary": "Dùng `have been working`. Câu tiếp theo.",
    })
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value=payload)):
        fb = await client.evaluate("Tôi làm ở đây 3 năm.", "I work here for 3 years")
    assert isinstance(fb, Feedback)
    assert "have been working" in fb.vi_summary


async def test_evaluate_malformed_json_raises(system_prompt):
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value="not json")):
        with pytest.raises(FeedbackParseError):
            await client.evaluate("vi", "en")
