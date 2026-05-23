"""Stateless Claude Agent SDK wrapper.

Each public method creates a fresh query — no session reuse. The bot is
stateless per round (see spec §Architecture).

The exact SDK call shape is centralised in `_query()`. If the SDK API
changes, edit only that method. Callers depend on string in / string out.

Implementation note: uses the top-level `query()` function rather than
`ClaudeSDKClient` because we never need bidirectional communication; the
SDK docs recommend `query()` for exactly this stateless, fire-and-forget
pattern.
"""
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

from english_bot.models import Feedback


class ClaudeClient:
    def __init__(self, system_prompt_path: Path):
        self._system_prompt = system_prompt_path.read_text(encoding="utf-8")

    async def generate_prompt(self) -> str:
        """Nhiệm vụ A — return a fresh Vietnamese sentence (single line)."""
        user = "Sinh 1 câu (Nhiệm vụ A). Trả về duy nhất câu Vi, không quotes, không giải thích."
        raw = await self._query(user)
        return raw.strip().splitlines()[0].strip() if raw.strip() else ""

    async def evaluate(self, vi_prompt: str, transcript: str) -> Feedback:
        """Nhiệm vụ B — evaluate the user's English transcript against the Vi prompt."""
        user = (
            "Nhiệm vụ B. Đánh giá transcript dưới đây.\n\n"
            f"Vi prompt: {vi_prompt}\n"
            f"English transcript: {transcript}\n\n"
            "Trả về JSON duy nhất, đúng schema 4 fields."
        )
        raw = await self._query(user)
        return Feedback.from_json(raw)

    async def _query(self, user_message: str) -> str:
        """Single fresh stateless query to Claude.

        Uses the top-level `query()` async generator — recommended by the SDK
        for stateless, one-shot interactions. Returns the model's text response
        (concatenation of text blocks from AssistantMessage, or ResultMessage.result
        as fallback).
        """
        options = ClaudeAgentOptions(system_prompt=self._system_prompt)
        chunks: list[str] = []
        async for msg in await query(prompt=user_message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    text = getattr(block, "text", None)
                    if text:
                        chunks.append(text)
            elif isinstance(msg, ResultMessage):
                if not chunks and isinstance(msg.result, str):
                    chunks.append(msg.result)
        return "".join(chunks).strip()
