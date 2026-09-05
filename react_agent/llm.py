"""Thin wrapper around the Anthropic API. Requires ANTHROPIC_API_KEY in the env."""
import anthropic

_client = anthropic.Anthropic()


def complete(prompt: str, stop: list[str] | None = None, model: str = "claude-haiku-4-5-20251001") -> str:
    resp = _client.messages.create(
        model=model,
        max_tokens=512,
        stop_sequences=stop or [],
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
