---
type: knowledge
summary: Origin plan for pairing hands-on building with the AI papers reading — four build options tied to papers already read; superseded as the project scaffold by _overview.md, kept for the option rationale and the detailed nano-Transformer milestone plan.
tags: [AI, agents, reading, planning, build]
status: active
owner: Ayush Sood
updated: 2026-09-09
related: "[_overview.md](_overview.md), [references.md](references.md), [../ai-papers-reading/_overview.md](../ai-papers-reading/_overview.md), [../fastapi-reading/_overview.md](../fastapi-reading/_overview.md)"
---

# Build Guide — Pairing Building with the AI Papers Reading

**Status:** this was the original plan, written while it still lived inside `ai-papers-reading`. The project is now scaffolded — see [_overview.md](_overview.md) for how it actually operates (you drive; the specs are stuck-buttons). This file is kept for the *why each option matters* rationale and the detailed nano-Transformer milestone plan below.

## Why build at all

Reading tells you *what* these mechanisms are; building is what exposes the parts you only think you understand. Each paper read so far maps to something concretely buildable, in escalating difficulty.

| Paper read | What building it forces you to actually understand |
|---|---|
| Attention Is All You Need | Self-attention isn't a metaphor — hand-writing the QKV matmuls and watching attention weights form |
| Chain-of-Thought | Why prompting alone changes output — seeing it stop working below a certain model size, firsthand |
| ReAct | The think → act → observe loop, and where it breaks (infinite loops, bad tool choice, parsing failures) |
| Toolformer | The filtering math already verified — turns from "an equation I checked" into "a script that actually decides" |

## Four concrete build options, easiest → hardest

**1. Nano-Transformer from scratch (no framework)**
Implement multi-head self-attention, positional encoding, and train a tiny char-level language model (Karpathy's "let's build GPT" territory — see [references.md](references.md) for nn-zero-to-hero). Pure NumPy or minimal PyTorch. Best return for the Attention reading — nothing cements "how attention actually works" like writing the matmuls yourself. Weekend-scale project. No separate spec for this one by design — write your own approach first.

**2. Hand-rolled ReAct agent, no LangChain/framework**
Raw LLM API calls, a manual parsing loop for `Thought:`/`Action:`/`Observation:`, 2–3 real tools (calculator, a search API). Surfaces ReAct's actual failure modes directly: the model hallucinating a tool that doesn't exist, malformed action syntax, infinite think-loops with no termination. Directly operationalizes Paper 2, and is the natural place to reuse the FastAPI reading — wrap it as a small FastAPI service. Full spec: [react-agent-spec.md](react-agent-spec.md).

**3. Toolformer-lite: build the actual filtering pipeline**
Take a small open-weight model (something logprobs are actually accessible for — a local Pythia/GPT-2 class model via HuggingFace, not a closed API), sample candidate tool-call insertions, compute the real `L_i^- - L_i^+ ≥ τ_f` criterion, and see what it actually keeps vs. discards on real text. Most research-flavored of the four — genuinely hard because it needs token-level logprobs, which most hosted APIs don't expose. Best done after option 1, once "what `p_M` computes" isn't a black box anymore. Full spec: [toolformer-lite-spec.md](toolformer-lite-spec.md).

**4. Tie it together: expose ReAct-style tools as an MCP server**
The `fastapi-reading` project already has an explainer for how `fastapi_mcp` works. Expose the tools from option 2 (not necessarily the whole agent loop) via `fastapi_mcp`, so an actual MCP client (Claude Desktop, etc.) does the reasoning-and-acting externally, against tools you built. Connects three reading threads into one artifact: agent-loop mechanics (AI papers) + FastAPI service (FastAPI project) + MCP exposure (also FastAPI project). Full spec: [react-mcp-server-spec.md](react-mcp-server-spec.md).

## Option 1, Detailed Plan — Nano-Transformer From Scratch

Suggested as the starting point. This is the one build with no AI-written spec — the milestone list below is the only scaffold, and you fill in shapes and code yourself (lean on [references.md](references.md) — nn-zero-to-hero lecture 7 covers exactly this).

### What you'll gain

- **The actual mechanics of self-attention** (Q/K/V projections, scaled dot-product, softmax) as code you wrote, not a function you called.
- **Why the `1/√d_k` scaling exists** — without it, dot products grow with dimension and push softmax into saturated, near-zero-gradient regions. You'll be able to explain this instead of reciting it.
- **Why causal masking exists** — the mechanical reason a decoder-only LM can't "see the future" during training, and how that same mask is what makes autoregressive generation coherent at inference.
- **Why positional encoding is necessary at all** — attention is permutation-invariant by construction; order is not free the way it is in an RNN. You'll see this by literally removing it and watching the model lose word-order sensitivity.
- **Why multi-head attention helps** — running several smaller attention operations in parallel with independent projections, rather than one large one, and what that buys over a single head.
- **Why residual connections + LayerNorm matter for depth** — stack a few blocks without them and watch training destabilize; that failure is the lesson.
- **A direct, literal connection to Toolformer's math you already verified** — `p_M(x_j | z, x_{1:j-1})` stops being a symbol from a paper and becomes a function you implemented and can trace a value through.
- **A toy, hands-on echo of Paper 1's emergent-abilities discussion** — train the same architecture at a couple of depths/widths on the same data and watch whether capability shows up gradually or suddenly, on a scale small enough to actually inspect.
- **Practical PyTorch mechanics** — batched matmuls, tensor reshaping for multi-head splits, causal masking via `masked_fill`, a real training loop, and sampling/generation.
- **Interview value** — "explain self-attention" and "why do we need positional encodings" turn into things you've implemented rather than memorized definitions; this comes up often in ML/AI engineering interviews.

### Tooling

- **PyTorch, not pure NumPy.** Pure NumPy would mean hand-deriving backpropagation through softmax and attention — a large separate project in matrix calculus that doesn't actually teach *this* paper's ideas. PyTorch's autodiff lets the focus stay on architecture and shapes, which is where the actual understanding lives.
- **Don't call `nn.MultiheadAttention`.** The entire point is writing the QKV projections, the scaled dot product, the mask, and the softmax yourself. Use plain `nn.Linear` and tensor ops for everything else.
- **Dataset: tinyshakespeare** (the standard small char-level corpus used in Karpathy's own walkthrough) — small enough to train on a CPU or a free Colab GPU in minutes, and well-trodden enough that if something looks wrong, it's easy to tell whether it's a bug or expected behavior.

### Milestones, in order

1. **Bigram baseline (no attention at all).** A trivial lookup-table model, just to get the data pipeline, batching, loss, and generation loop working end-to-end before any architecture complexity. Confirms the scaffolding works before attention is added on top.
2. **Single self-attention head.** Q, K, V linear projections → scaled dot-product scores → causal mask (lower-triangular) → softmax → weighted sum with V. This is the paper's core equation, implemented directly.
3. **Multi-head attention.** Several heads in parallel with independent projections, concatenated and projected back down.
4. **Positional encoding.** Sinusoidal (as in the original paper) or a simpler learned embedding — added on top of token embeddings before the first block.
5. **Full Transformer block.** Attention sublayer + feedforward (MLP) sublayer, each wrapped in a residual connection and LayerNorm (pre-norm, the modern stable convention).
6. **Stack blocks and train.** Several blocks deep, train on tinyshakespeare, watch the loss curve, sample generated text at increasing training steps to see coherence emerge.
7. **Optional stretch — compare against the bigram baseline** on held-out loss and sample quality, to see concretely what attention buys over no attention at all, and optionally compare a couple of depths/widths to connect back to the emergent-abilities discussion from Paper 1.

## Recommendation

A reasonable order is **1 → 2** — nano-Transformer first (self-contained, directly rewards the Attention reading), then the hand-rolled ReAct agent (rewards Paper 2, sets up for option 4 later), with 3 and 4 as follow-ons. But per the project's operating principle, this is a suggestion, not a route — pick whatever you actually want to build.

The open question this file used to end on — *scaffold a dedicated project or not* — is resolved: the project was scaffolded on 2026-09-09 as `1-Projects/build-ai/`.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-05 | Plan written, not yet started | Ayush Sood |
| 2026-09-05 | Added detailed milestone plan for option 1, and full technical specs for options 2-4 | Ayush Sood |
| 2026-09-09 | Moved into new `build-ai` project; superseded as scaffold by `_overview.md`; removed dangling reference to a nano-transformer-spec that was never committed | Ayush Sood |
