import pytest
from english_bot.models import Feedback, FeedbackParseError


def test_feedback_from_json_happy_path():
    payload = '''
    {
      "transcript": "I have been working here for 3 years",
      "evaluation_text": "Cấu trúc đúng, dùng present perfect continuous tốt.",
      "model_english": "I have been working here for three years.",
      "vi_summary": "Dùng `have been working` chuẩn rồi đó. Câu tiếp theo."
    }
    '''
    fb = Feedback.from_json(payload)
    assert fb.transcript.startswith("I have been")
    assert fb.model_english.startswith("I have been")
    assert "have been working" in fb.vi_summary


def test_feedback_from_json_missing_field_raises():
    payload = '{"transcript": "x", "evaluation_text": "y", "model_english": "z"}'
    with pytest.raises(FeedbackParseError, match="vi_summary"):
        Feedback.from_json(payload)


def test_feedback_from_json_malformed_raises():
    with pytest.raises(FeedbackParseError, match="JSON"):
        Feedback.from_json("not json at all")


def test_feedback_from_json_extracts_from_code_fence():
    # Claude often wraps JSON in ```json ... ``` fences. Strip them.
    payload = '''```json
    {"transcript": "a", "evaluation_text": "b", "model_english": "c", "vi_summary": "d"}
    ```'''
    fb = Feedback.from_json(payload)
    assert fb.transcript == "a"


def test_feedback_from_json_null_payload_raises():
    with pytest.raises(FeedbackParseError, match="expected a JSON object"):
        Feedback.from_json("null")


def test_feedback_from_json_array_payload_raises():
    with pytest.raises(FeedbackParseError, match="expected a JSON object"):
        Feedback.from_json('[{"transcript": "x"}]')


def test_feedback_from_json_uppercase_fence_works():
    payload = '''```JSON
    {"transcript": "u", "evaluation_text": "v", "model_english": "w", "vi_summary": "x"}
    ```'''
    fb = Feedback.from_json(payload)
    assert fb.transcript == "u"
