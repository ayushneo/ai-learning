---
type: knowledge
summary: Full technical spec and code guide for building a nano-Transformer from scratch in PyTorch — shapes, skeletons (not full solutions), trade-offs, and debugging checkpoints, for self-implementation.
tags: [AI, agents, reading, architecture, transformers, build]
status: draft
owner: Ayush Sood
updated: 2026-09-05
related: "[build-guide.md](build-guide.md), [_overview.md](_overview.md), [2026-09-03-notes-attention.md](2026-09-03-notes-attention.md)"
---

# Nano-Transformer From Scratch — Spec & Code Guide

Skeletons and shapes, not finished code — write the actual tensor math yourself. Where a `# TODO` appears, that line is the thing to implement; everything else is scaffolding.

## Project structure

```
nano_transformer/
  data.py        tokenizer + batching
  model.py       attention head, multi-head, block, full model
  train.py       training loop
  generate.py    sampling/generation
  config.py      hyperparameters
```

## Hyperparameters

Start absurdly small to iterate fast, scale up once correct:

| Param | Debug scale | "Real" scale (needs a GPU) |
|---|---|---|
| `n_embd` | 32 | 384 |
| `n_head` | 4 | 6 |
| `n_layer` | 2 | 6 |
| `block_size` (context length) | 8 | 256 |
| `batch_size` | 16 | 64 |
| `dropout` | 0 | 0.1–0.2 |

**Developer note:** set `dropout=0` while debugging the pipeline. Dropout adds stochasticity that can mask a real bug as "just noise" — only turn it on once you trust the mechanics are correct.

## Data & tokenizer

- Char-level vocabulary: `chars = sorted(set(text))`, build `stoi`/`itos` dicts, `encode`/`decode` functions.
- 90/10 train/val split.
- `get_batch(split)`: randomly sample `batch_size` windows of length `block_size`; `y` is `x` shifted by one position (next-token targets). Both shapes: `(batch_size, block_size)`.

**Trade-off — char-level vs. BPE tokenization:** char-level is far simpler to implement and keeps the whole exercise focused on the architecture rather than tokenization. It costs you compression (more tokens per unit of meaning, so you need a longer context for the same semantic span) — a real, deliberate trade-off, not a shortcut you should feel bad about.

## Self-attention head — the core equation

```python
class Head(nn.Module):
    def __init__(self, n_embd, head_size, block_size, dropout):
        super().__init__()
        self.key = nn.Linear(n_embd, head_size, bias=False)
        self.query = nn.Linear(n_embd, head_size, bias=False)
        self.value = nn.Linear(n_embd, head_size, bias=False)
        self.register_buffer('tril', torch.tril(torch.ones(block_size, block_size)))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        # x: (B, T, C)   B=batch, T=sequence length, C=n_embd
        B, T, C = x.shape
        k = self.key(x)    # (B, T, head_size)
        q = self.query(x)  # (B, T, head_size)
        v = self.value(x)  # (B, T, head_size)

        # TODO: attention scores — q @ k.transpose(-2, -1) * head_size**-0.5   -> (B, T, T)
        # TODO: causal mask — wei.masked_fill(self.tril[:T, :T] == 0, float('-inf'))
        # TODO: softmax over the last dimension
        # TODO: dropout on the attention weights
        # TODO: weighted aggregation — wei @ v   -> (B, T, head_size)
        return out
```

**Shape checkpoints:** `wei` before masking is `(B, T, T)`; after softmax, every row should sum to `1.0` — assert this once while building. Output is `(B, T, head_size)`.

**Trade-off — why scale by `head_size**-0.5`, not `n_embd**-0.5`:** the scaling has to match the dimensionality of the actual dot product (the per-head vectors), not the full embedding. Get this wrong and dot products grow with dimension, pushing softmax into saturated, near-zero-gradient regions — training will look fine at small scale and quietly degrade as you increase `head_size`.

**Developer note — `register_buffer` for `tril`:** it's not a learnable parameter, but it does need to move to whatever device the model is on. A plain attribute won't get device-managed by PyTorch; `register_buffer` will.

## Multi-head attention

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, n_embd, n_head, block_size, dropout):
        super().__init__()
        head_size = n_embd // n_head
        self.heads = nn.ModuleList([Head(n_embd, head_size, block_size, dropout) for _ in range(n_head)])
        self.proj = nn.Linear(n_embd, n_embd)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        # TODO: run every head, concatenate along the last dim -> (B, T, n_embd)
        # TODO: project back down through self.proj, then dropout
        return out
```

**Developer note:** `n_embd` must be divisible by `n_head` — assert this explicitly early on. Getting it wrong is a silent shape bug, not a crash you'll immediately understand.

**Trade-off — list of `Head` modules vs. one batched op:** the list-of-heads version above is what's written here because it's the clearest to read and debug the first time — you can inspect one head in isolation. Real implementations (nanoGPT, HuggingFace) instead reshape into `(B, n_head, T, head_size)` and do the attention math once, batched, for speed. Recommendation: build the readable version first, get it working, then optionally refactor to the batched version — the refactor itself is a good exercise in *why* the batched form is equivalent.

## Positional encoding

Two real options, not just one "correct" answer:

- **Learned** (`nn.Embedding(block_size, n_embd)`, added to token embeddings) — simpler, what most modern small implementations (including nanoGPT) use. Trade-off: cannot generalize to sequences longer than the trained `block_size` at all.
- **Sinusoidal** (the original paper's choice): `PE(pos, 2i) = sin(pos / 10000^(2i/d_model))`, `PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))` — fixed, not learned. Trade-off: more implementation work, and in principle extrapolates to unseen lengths better, though this has been largely superseded in modern practice (e.g. RoPE) rather than actually relied on.

**Recommendation:** implement learned embeddings first to get the full pipeline training end to end. Then implement sinusoidal separately as a direct comparison against what the paper you read actually specifies — that comparison is itself worth more than either implementation alone.

## Feedforward (MLP) sublayer

```python
class FeedForward(nn.Module):
    def __init__(self, n_embd, dropout):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd),
            nn.ReLU(),
            nn.Linear(4 * n_embd, n_embd),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        return self.net(x)
```

**Developer note:** the 4× expansion factor (`d_ff = 4 * d_model`) is the paper's own convention — not a value to agonize over, just replicate it.

## Transformer block

```python
class Block(nn.Module):
    def __init__(self, n_embd, n_head, block_size, dropout):
        super().__init__()
        self.sa = MultiHeadAttention(n_embd, n_head, block_size, dropout)
        self.ffwd = FeedForward(n_embd, dropout)
        self.ln1 = nn.LayerNorm(n_embd)
        self.ln2 = nn.LayerNorm(n_embd)

    def forward(self, x):
        # TODO: x = x + self.sa(self.ln1(x))      pre-norm + residual, attention sublayer
        # TODO: x = x + self.ffwd(self.ln2(x))    pre-norm + residual, feedforward sublayer
        return x
```

**Trade-off — pre-norm vs. post-norm:** the skeleton above is pre-norm (LayerNorm applied *before* each sublayer, as written). The original 2017 paper actually specifies post-norm (LayerNorm *after* each sublayer, applied to the sum). Pre-norm trains far more stably at depth and is what essentially every modern implementation (GPT-2 onward) actually uses; post-norm is what "Attention Is All You Need" literally says. Worth knowing both exist. If you want to feel *why* the field moved to pre-norm rather than just accepting it, implement post-norm once and watch what happens to training stability as you add layers.

## Full model

```python
class NanoTransformer(nn.Module):
    def __init__(self, vocab_size, n_embd, n_head, n_layer, block_size, dropout):
        super().__init__()
        self.token_embedding = nn.Embedding(vocab_size, n_embd)
        self.position_embedding = nn.Embedding(block_size, n_embd)
        self.blocks = nn.Sequential(*[Block(n_embd, n_head, block_size, dropout) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(n_embd)
        self.lm_head = nn.Linear(n_embd, vocab_size)

    def forward(self, idx, targets=None):
        B, T = idx.shape
        # TODO: tok_emb = self.token_embedding(idx)                    (B, T, n_embd)
        # TODO: pos_emb = self.position_embedding(torch.arange(T))     (T, n_embd)
        # TODO: x = tok_emb + pos_emb
        # TODO: x = self.blocks(x)
        # TODO: x = self.ln_f(x)
        # TODO: logits = self.lm_head(x)                               (B, T, vocab_size)
        loss = None
        if targets is not None:
            # TODO: reshape logits -> (B*T, vocab_size), targets -> (B*T,)
            # TODO: loss = F.cross_entropy(logits, targets)
            pass
        return logits, loss

    def generate(self, idx, max_new_tokens):
        for _ in range(max_new_tokens):
            # TODO: crop idx to the last block_size tokens before the forward pass
            # TODO: get logits from self(idx_cropped) — ignore loss
            # TODO: take logits at the last time step, softmax over vocab
            # TODO: sample with torch.multinomial (or argmax for greedy), append to idx
            pass
        return idx
```

**Critical developer note:** in `generate`, cropping `idx` to the last `block_size` tokens before every forward pass is not optional. The position embedding table only has `block_size` rows — feed it a longer index and it crashes. This is the single most common bug at generation time, and it won't show up until generation runs longer than `block_size` tokens, so it can pass early testing and fail later.

## Training loop

```python
model = NanoTransformer(...)
optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

for iter in range(max_iters):
    xb, yb = get_batch('train')
    logits, loss = model(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()
    if iter % eval_interval == 0:
        # TODO: estimate_loss() — average loss over several batches for both splits, print
```

**Developer note:** report loss averaged over several batches (`estimate_loss()`), not a single batch's loss. A single batch is noisy enough to make a correctly-training model look broken.

## Debugging / verification checkpoints — do these before trusting any result

1. **Overfit a tiny subset first.** Train on a handful of examples for many iterations and confirm loss → ~0. If the model can't memorize a handful of examples, there's a bug — don't move to the full dataset until this passes.
2. **Shape-assert everything early.** Print or assert tensor shapes at every module boundary on the first run; strip the prints once confirmed.
3. **Softmax rows sum to 1** in the attention head — assert this once.
4. **Causal mask sanity check.** Print or visualize the attention weight matrix for one example — the upper triangle should be exactly 0 after masking and softmax.
5. **Initial loss should be close to `-ln(1/vocab_size)`** (random-guessing loss) before any training happens — for a 65-character vocab, that's ≈ 4.17. If the very first loss is far from that, something's wrong in initialization or the loss computation, not in learning dynamics.
6. **Generation should degrade gracefully.** Early in training, generated text should look close to random characters. Suspiciously "clean" output immediately is a sign of a bug (e.g. the model copying input) rather than a good sign.

## Trade-offs, summarized

| Decision | Options | Recommendation & why |
|---|---|---|
| Autodiff | Pure NumPy vs. PyTorch | PyTorch — keeps the focus on architecture, not re-deriving backprop through softmax by hand |
| Tokenizer | Char-level vs. BPE | Char-level — avoids an unrelated complexity, keeps the exercise about attention |
| Positional encoding | Learned vs. sinusoidal | Learned first for simplicity; implement sinusoidal after, as a direct comparison against the paper |
| Norm placement | Pre-norm vs. post-norm | Pre-norm for training stability (modern standard); implement post-norm once to feel why the field moved away from it |
| Multi-head implementation | List of `Head` modules vs. batched reshape | List first, for readability/debuggability; batch it later, once correct, for speed |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-05 | Spec written — skeletons, shapes, trade-offs, debugging checkpoints. Not yet implemented. | Ayush Sood |
