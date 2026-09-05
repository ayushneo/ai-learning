---
type: knowledge
summary: Full technical spec and code guide for exposing ReAct-style tools as an MCP server via fastapi_mcp — architecture choice, code skeleton, trade-offs, and debugging checkpoints, for self-implementation.
tags: [AI, agents, reading, tool-use, fastapi, mcp, build]
status: draft
owner: Ayush Sood
updated: 2026-09-05
related: "[build-guide.md](build-guide.md), [_overview.md](_overview.md), [react-agent-spec.md](react-agent-spec.md), [../fastapi-reading/2026-08-28-how-fastapi-mcp-works.md](../fastapi-reading/2026-08-28-how-fastapi-mcp-works.md)"
---

# ReAct Tools as an MCP Server — Spec & Code Guide

Skeletons and shapes, not finished code. This build ties three reading threads together: agent-loop mechanics (this project), FastAPI (`fastapi-reading`), and MCP exposure via `fastapi_mcp` (also `fastapi-reading` — see the linked explainer for how the library works internally before starting this).

## The key architectural choice — read this before writing any code

There are two genuinely different things you could build here, and they teach different lessons:

**(a) Expose the individual tools** (calculator, search) as FastAPI endpoints, and let `fastapi_mcp` turn *those* into MCP tools. An external MCP client (Claude Desktop, Claude Code, etc.) becomes the reasoning loop — it decides when to call which tool, in what order. You are not writing a ReAct loop at all in this version; you're handing your tools to something that already has one.

**(b) Expose the whole hand-rolled agent** from `react-agent-spec.md` as a single meta-tool (e.g. `ask_agent(question)` that runs your ReAct loop internally and returns a final answer). Simpler to wire up, but hides all the interesting tool-selection structure from the MCP client — from the outside it looks like one big opaque tool.

**Recommendation: build (a).** It's the more valuable exercise — it's also the more honest use of `fastapi_mcp` (matching what the library is actually for, per its own README: exposing FastAPI endpoints as tools, not wrapping an existing agent), and it's a direct, concrete way to see an external LLM client do ReAct-style reasoning against tools you built, without you writing the loop yourself this time. Treat (b) as, at most, a quick five-minute contrast afterward — not the main artifact.

## Project structure

```
react_mcp_server/
  main.py         FastAPI app + tool endpoints
  tools.py        tool implementations (reuse from the react-agent build)
  mcp_setup.py    FastApiMCP wiring
```

## Code skeleton — option (a)

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi_mcp import FastApiMCP

app = FastAPI(title="ReAct Tools")

class CalculatorInput(BaseModel):
    expression: str = Field(..., description="A basic arithmetic expression, e.g. '12 * (4 + 1)'")

class CalculatorOutput(BaseModel):
    result: float

@app.post("/calculator", operation_id="calculator", response_model=CalculatorOutput)
async def calculator(input: CalculatorInput) -> CalculatorOutput:
    # TODO: safely evaluate input.expression — reuse the tool from react-agent-spec.md
    ...

class SearchInput(BaseModel):
    query: str = Field(..., description="A search query, e.g. a factual question")

class SearchOutput(BaseModel):
    snippet: str

@app.post("/search", operation_id="search", response_model=SearchOutput)
async def search(input: SearchInput) -> SearchOutput:
    # TODO: reuse the search tool from react-agent-spec.md
    ...

mcp = FastApiMCP(app, name="React Tools MCP", describe_full_response_schema=True)
mcp.mount_http()
```

## Developer notes, directly from the fastapi_mcp explainer already written

- **Set `operation_id` explicitly on every route**, as above. Per the explainer's own flagged gotcha: the MCP tool name *is* the `operationId`. Leave it to FastAPI's auto-generation and an unrelated refactor (renaming the function, moving the route) can silently rename or break the tool from an agent's perspective.
- **`Field(..., description=...)` is not optional decoration** — tool quality is entirely downstream of this. The description is literally what an LLM client sees when deciding whether and how to call the tool. Write these as if you're documenting for another AI, because that's exactly the audience.
- **No filtering configured here means both tools are exposed** — fine for two harmless tools, but the explainer's biggest flagged risk (default behavior is "expose everything") still applies in spirit. Get in the habit of thinking about exposure surface even on a two-tool toy project, since that habit is the actual point of reading that explainer.
- **The calculator's `eval()`-style safety concern carries over unchanged** from the ReAct agent build — still a personal/local toy, not something to expose past your own machine as-is.

## Debugging / verification checkpoints

1. **Test each FastAPI endpoint directly first**, via the auto-generated `/docs` Swagger UI, before touching MCP at all. Confirm the tools work as plain HTTP endpoints on their own.
2. **Connect an actual MCP client** (Claude Desktop's config pointing at `mount_http()`'s endpoint, or `mcp-remote`) and confirm it lists both tools with sensible, specific descriptions. Generic-sounding tool descriptions in the client are the OpenAPI-hygiene point from the explainer made concrete and visible.
3. **Ask the connected client a question that plausibly needs both tools in sequence**, and watch whether *it* does the reasoning-then-acting on its own. This is the actual payoff of building (a) instead of (b) — you're observing ReAct-style behavior in a system you didn't write the loop for.

## Trade-offs, summarized

| Decision | Options | Recommendation & why |
|---|---|---|
| What to expose | Individual tools (a) vs. the whole agent as one meta-tool (b) | (a) — more honest use of the library, and the reasoning loop happens externally where you can actually observe it |
| Tool descriptions | Minimal vs. detailed `Field(description=...)` | Detailed — this is the entire quality signal an MCP client has to work with |
| `operation_id` | Auto-generated vs. explicit | Explicit, always, for anything meant to stay a stable tool identity |
| Filtering | None vs. `include_tags`/`exclude_operations` | None needed for 2 harmless tools, but treat the decision as deliberate, not an oversight |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-05 | Spec written — architecture choice, code skeleton, trade-offs, debugging checkpoints. Not yet implemented. | Ayush Sood |
