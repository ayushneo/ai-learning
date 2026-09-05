---
type: knowledge
summary: Full technical spec and code guide for building a Toolformer-lite filtering pipeline — sampling, loss computation, the filtering criterion, trade-offs, and debugging checkpoints, for self-implementation.
tags: [AI, agents, reading, tool-use, build]
status: draft
owner: Ayush Sood
updated: 2026-09-05
related: "[build-guide.md](build-guide.md), [_overview.md](_overview.md), [2026-09-02-notes-toolformer.md](2026-09-02-notes-toolformer.md)"
---

# Toolformer-Lite Filtering Pipeline — Spec & Code Guide

Skeletons and shapes, not finished code — write the actual tensor math yourself. This is the hardest of the four build options: it requires token-level log-probabilities, which most hosted LLM APIs don't expose, so this needs a local open-weight model.

## Scope of the "lite" version, stated up front

This implements the filtering math verified directly against the paper (in `2026-09-02-notes-toolformer.md`), applied to a single tool. It deliberately **simplifies candidate generation** — the full paper prompts the model itself to propose plausible call positions and inputs, which needs a capable model steered by a careful few-shot prompt. The lite version uses a cheap heuristic instead (details below). This is a real simplification, not a shortcut to be quietly embarrassed about — the part worth understanding deeply here is the filtering criterion, not the candidate-proposal mechanism.

## Project structure

```
toolformer_lite/
  model.py       load a HuggingFace model + tokenizer
  candidates.py  heuristic candidate position generation
  scoring.py     L_i^+, L_i^-, the filtering criterion, the weight function
  tools.py       a Calculator tool
  pipeline.py    ties it together over a small text corpus
```

## Model choice

Needs a real base language model you can get logits/log-probs from directly — GPT-2-small (124M, well-documented, runs on CPU) or Pythia-160m/410m (more modern internals, similarly small) via HuggingFace `transformers`. **Not** a hosted API — this is the one build option where that constraint is non-negotiable, since the entire method depends on `log p_M(x_j | z, x_{1:j-1})`.

## Step 1 — candidate positions (heuristic, not the paper's own method)

For a first pass, skip prompting the model to propose calls. Use a cheap heuristic instead, mirroring the spirit of what the paper itself does for *bootstrapping* certain tools: only consider inserting a `Calculator` call at positions where a number appears in the text, since that's where a calculator result is plausibly relevant.

```python
def find_candidate_positions(text: str, tokenizer) -> list[int]:
    # TODO: tokenize, then find token positions immediately after a numeric token
    #       (or, simpler: positions right before a sentence containing arithmetic-looking text)
    ...
```

**Trade-off:** loses the paper's "fully self-supervised, no per-tool heuristic" purity, but is far simpler to implement and keeps the interesting part (the filtering criterion) front and center rather than buried under prompt engineering for a candidate-generation step.

## Step 2 — the weighted loss (direct implementation of the verified equation)

From the notes: `L_i(z) = -Σ_{j=i}^{n} w_{j-i} · log p_M(x_j | z, x_{1:j-1})`.

```python
def compute_loss(model, tokenizer, prefix_ids, target_ids, weight_fn) -> float:
    # TODO: concatenate prefix_ids + target_ids, run through the model in one
    #       forward pass, get logits
    # TODO: shift logits/targets by one position (standard next-token setup:
    #       logits[t] predicts target_ids[t+1])
    # TODO: apply log_softmax to logits, gather the log-prob of each true
    #       target token at its position
    # TODO: weight each position's log-prob by weight_fn(position_from_start),
    #       sum, negate — this is L_i(z)
    ...
```

## Step 3 — the weight function (already verified — implement as-is)

`w_t = w̃_t / Σ w̃_s`, with `w̃_t = max(0, 1 - 0.2·t)`.

```python
def weight_fn(t: int, max_t: int = 5) -> float:
    # TODO: raw = max(0, 1 - 0.2 * t)
    # TODO: normalize by the sum of raw weights over t=0..max_t (raw is 0 past t=5 anyway)
    ...
```

## Step 4 — the two baselines and the keep criterion

```python
def score_candidate(model, tokenizer, x, i, api_call, result) -> bool:
    prefix_with_result = linearize(api_call, result)      # e(c_i, r_i)
    prefix_call_only   = linearize(api_call, None)         # e(c_i, ε)
    prefix_empty       = ""                                 # ε

    target = x[i:]  # tokens after position i, up to the weighting window

    # TODO: L_plus  = compute_loss(model, tokenizer, prefix_with_result, target, weight_fn)
    # TODO: L_minus = min(
    #           compute_loss(model, tokenizer, prefix_empty, target, weight_fn),
    #           compute_loss(model, tokenizer, prefix_call_only, target, weight_fn),
    #       )
    # TODO: return (L_minus - L_plus) >= tau_f
    ...
```

## Trade-offs, summarized

| Decision | Options | Recommendation & why |
|---|---|---|
| Model | Hosted API vs. local HF model | Local — this is the one option where the constraint is hard, not stylistic; you need real token log-probs |
| Candidate generation | Full self-supervised prompting vs. heuristic | Heuristic first — keeps focus on the filtering math, which is the actual point of this build |
| Tool | Calculator vs. something else | Calculator — deterministic, cheap to execute, and literally the paper's own Table 1 example |
| `τ_f` | Fixed guess vs. swept range | Sweep it (see checkpoint 3) — a single fixed value tells you nothing about the method's actual behavior |

## Debugging / verification checkpoints

1. **Sanity-check `compute_loss` in isolation first**, before touching the filtering logic. Feed the model an easy, obviously-correct next word and confirm loss is low; feed an obviously-wrong one and confirm loss is high. If this doesn't hold in both directions, the bug is in the loss computation, not the method.
2. **Verify `L_i^+ < L_i^-` on an obviously-helpful example** — e.g. insert the correct arithmetic answer directly before a sentence that references it (`"...costs 3 * 4 = [Calculator(3*4) -> 12] 12 dollars"`). If this doesn't hold on a case this obvious, the bug is in your loss computation or baseline construction, not in the underlying idea.
3. **Sweep `τ_f` and plot how many candidates survive** at each threshold, the same way the paper's own Table 2 reports counts per threshold. Compare the shape of your kept-vs-discarded curve against that intuition — a threshold sweep tells you far more than any single fixed value.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-05 | Spec written — skeletons, scoring pipeline, trade-offs, debugging checkpoints. Not yet implemented. | Ayush Sood |
