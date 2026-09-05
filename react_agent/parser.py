"""Strict parser for ReAct-formatted model output.

Strict on purpose: this is meant to surface the model's real formatting
failures, not paper over them with fuzzy matching.
"""
import re

_FINAL_RE = re.compile(r"Final Answer:\s*(.+)", re.DOTALL)
_ACTION_RE = re.compile(r"Action:\s*(.+?)\nAction Input:\s*(.+)", re.DOTALL)


def parse_llm_output(text: str) -> dict:
    final_match = _FINAL_RE.search(text)
    if final_match:
        return {"type": "final", "answer": final_match.group(1).strip()}

    action_match = _ACTION_RE.search(text)
    if action_match:
        name = action_match.group(1).strip()
        tool_input = action_match.group(2).strip().splitlines()[0].strip()
        return {"type": "action", "name": name, "input": tool_input}

    return {"type": "parse_error", "raw": text}


def demo():
    assert parse_llm_output("Thought: done\nFinal Answer: 42") == {"type": "final", "answer": "42"}
    r = parse_llm_output("Thought: x\nAction: Calculator\nAction Input: 1 + 1\nObservation:")
    assert r == {"type": "action", "name": "Calculator", "input": "1 + 1"}
    assert parse_llm_output("garbage output")["type"] == "parse_error"
    print("parser.py: ok")


if __name__ == "__main__":
    demo()
