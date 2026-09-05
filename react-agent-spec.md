---
type: knowledge
summary: Full technical spec and code guide for building a hand-rolled ReAct agent from scratch (no framework) — parsing, loop design, trade-offs, and debugging checkpoints, for self-implementation.
tags: [AI, agents, reading, tool-use, build]
status: draft
owner: Ayush Sood
updated: 2026-09-05
related: "[build-guide.md](build-guide.md), [_overview.md](_overview.md), [2026-08-26-notes-react.md](2026-08-26-notes-react.md)"
---

# Hand-Rolled ReAct Agent — Spec & Code Guide

Skeletons and shapes, not finished code — write the actual logic yourself. Where a `# TODO` appears, that's the thing to implement.

## Project structure

```
react_agent/
  tools.py     tool implementations (calculator, search)
  prompt.py    the ReAct few-shot prompt template
  parser.py    parses model output into Thought/Action/Action Input/Final Answer
  llm.py       thin wrapper around whatever LLM API you use
  agent.py     the main loop
```

## The core loop, from the paper

The model generates in an interleaved format: `Thought: ...` → `Action: <tool>` → `Action Input: <input>`, the harness executes the tool and injects `Observation: <result>`, and the cycle repeats until the model emits `Final Answer: ...`. This is ReAct's actual mechanism, not an abstraction — you're implementing the paper's own prompting format directly.

## Design decision — text parsing vs. function-calling APIs

Modern LLM APIs (OpenAI/Anthropic tool-use, function calling) solve the parsing problem for you by returning structured JSON instead of freeform text. **Build the raw text-parsing version first anyway.** That's deliberate: the whole value of this exercise is feeling ReAct's actual failure modes — malformed output, hallucinated tool names, the model never converging — which a managed function-calling API hides from you entirely. Refactor to structured tool-calling afterward if you want a more robust version; don't start there.

## Prompt template (skeleton)

```
Answer the following question as best you can. You have access to the following tools:

{tool_descriptions}

Use this format:
Thought: reason about what to do next
Action: the tool to use, one of [{tool_names}]
Action Input: the input to the tool
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Question: {question}
```

Include 1–2 worked few-shot examples above the live question — zero-shot ReAct is meaningfully less reliable at following the exact format.

## Parsing

```python
def parse_llm_output(text: str) -> dict:
    # TODO: check for "Final Answer:" first — if present, return {"type": "final", "answer": ...}
    # TODO: else, regex-extract "Action: <name>" and "Action Input: <input>"
    # TODO: if neither pattern matches cleanly, return {"type": "parse_error", "raw": text}
    ...
```

**Trade-off — strict vs. lenient parsing:** strict parsing (fail loudly on anything that doesn't match exactly) surfaces the model's actual formatting failures, which is the point of building this by hand. Lenient/fuzzy parsing (tolerate extra whitespace, markdown fences, missing colons) produces a more robust agent but quietly hides how fragile the raw text format really is. Build strict first — you want to *see* the parse failures, not paper over them immediately.

## The agent loop

```python
def run_agent(question, tools, llm, max_iters=6):
    transcript = build_initial_prompt(question)
    for i in range(max_iters):
        # TODO: call llm(transcript, stop=["Observation:"]) — see note below on why `stop` matters
        # TODO: parse the output
        # TODO: if type == "final": return the answer
        # TODO: if type == "action": execute tools[name](input), append
        #       f"Observation: {result}\n" to the transcript, continue loop
        # TODO: if type == "parse_error": decide — retry once with a corrective
        #       message, or abort with the raw output for inspection
        pass
    # TODO: if the loop exhausts max_iters with no final answer, return a clear
    #       "gave up after N steps" result — never fail silently
```

**Critical developer note — the `stop` parameter.** If your LLM API supports stop sequences, pass `stop=["Observation:"]`. Without it, the model will frequently hallucinate its own fake observation text instead of waiting for the real tool result — a subtle bug that silently corrupts the loop rather than crashing it. This is one of the least obvious, most important details in actually building ReAct.

**Developer note — the iteration cap is not optional.** A model that never converges to `Final Answer` will loop forever without one, burning tokens (and money, on a paid API) indefinitely. This isn't defensive over-engineering — infinite/unproductive looping is one of ReAct's real, documented failure modes, and hitting it yourself is part of what this build teaches.

## Tools

- **Calculator** — evaluate a restricted arithmetic expression. **Safety note:** don't reach for raw `eval()` on arbitrary text beyond a local, personal toy project — fine here, explicitly *because* it never leaves your machine, not a pattern to carry into anything that takes input from anyone else.
- **Search** — the `wikipedia` Python package, or any search API you already have access to. Return a short text snippet, matching the paper's own tool shape (input → short text result).

## LLM choice

Hosted API (OpenAI/Anthropic/etc.) vs. a local model via Ollama. **Trade-off:** hosted APIs cost per call but reliably follow the ReAct output format; small local models are free but often fail at consistent formatting, which will show up as parse errors that are about model capability, not your code. If debugging feels like it's fighting the model rather than your logic, that's a sign to try a larger/hosted model before assuming your parser is broken.

## Debugging / verification checkpoints

1. **Log the full transcript at every step.** The raw text the model sees *is* the entire state — when something goes wrong, the transcript tells you exactly what the model saw and generated.
2. **Test each tool function standalone** before wiring it into the agent loop.
3. **Deliberately ask a question requiring 2+ tool calls** to confirm the loop actually re-invokes the LLM with the updated transcript, rather than just running once.
4. **Deliberately break something** — hand-edit a transcript to include a made-up tool name — and confirm your `parse_error` path actually triggers, rather than silently proceeding as if it were valid.

## Trade-offs, summarized

| Decision | Options | Recommendation & why |
|---|---|---|
| Output format | Freeform text parsing vs. structured function-calling | Text parsing first — feel ReAct's real failure modes before hiding them behind a managed API |
| Parsing strictness | Strict vs. lenient | Strict first — surfaces the model's actual formatting failures |
| LLM | Hosted API vs. local model | Hosted for reliability while debugging the agent logic itself; local once the logic is trusted |
| Loop safety | No cap vs. `max_iters` | Always cap — unbounded loops are a real ReAct failure mode, not a hypothetical |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-05 | Spec written — skeletons, prompt template, trade-offs, debugging checkpoints. Not yet implemented. | Ayush Sood |
