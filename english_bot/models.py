"""Data models for the bot."""
import json
import re
from dataclasses import dataclass


class FeedbackParseError(ValueError):
    """Raised when Claude's feedback payload is not valid JSON or is missing fields."""


@dataclass(frozen=True)
class Feedback:
    transcript: str
    evaluation_text: str
    model_english: str
    vi_summary: str

    @classmethod
    def from_json(cls, payload: str) -> "Feedback":
        text = _strip_code_fence(payload).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise FeedbackParseError(f"invalid JSON: {e}") from e
        try:
            return cls(
                transcript=data["transcript"],
                evaluation_text=data["evaluation_text"],
                model_english=data["model_english"],
                vi_summary=data["vi_summary"],
            )
        except KeyError as e:
            raise FeedbackParseError(f"missing field: {e.args[0]}") from e


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    m = _FENCE_RE.match(text)
    return m.group(1) if m else text
