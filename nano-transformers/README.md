# nano-transformers

A minimal, char-level GPT-style transformer implemented from scratch in PyTorch, following `nano-transformer-spec.md`.

## Files

| File | Purpose |
|---|---|
| `config.py` | Hyperparameters (debug scale by default) |
| `data.py` | Char-level tokenizer + batching |
| `model.py` | `Head`, `MultiHeadAttention`, `FeedForward`, `Block`, `NanoTransformer` |
| `train.py` | Training loop, saves `checkpoint.pt` |
| `generate.py` | Loads `checkpoint.pt` (if present) and samples text |
| `input.txt` | Sample training text (Hamlet's "To be, or not to be" soliloquy) |

## Usage

```bash
python train.py      # trains at debug scale, writes checkpoint.pt
python generate.py   # samples from checkpoint.pt, or a random model if none exists
```

Swap in your own text by replacing `input.txt` (or pointing `config.data_path` elsewhere), and switch `config.py` to the "real" scale hyperparameters once the debug scale trains correctly.

## Status

All TODOs from the spec are implemented and verified against its debugging checkpoints (softmax rows sum to 1, causal mask upper triangle is 0, initial loss ≈ `-ln(1/vocab_size)`, loss decreases with training).

Not implemented — left as optional follow-up exercises per the spec, each a deliberate comparison rather than a missing piece:

- **Sinusoidal positional encoding** — spec recommends learned embeddings first (done), sinusoidal after, as a comparison against the original paper.
- **Post-norm transformer block** — spec's `Block` is pre-norm (the modern standard); implementing post-norm once shows why the field moved away from it.
- **Batched multi-head attention** — `MultiHeadAttention` currently loops over a `ModuleList` of `Head`s for readability; reshaping into `(B, n_head, T, head_size)` for one batched op is a speed refactor for later.

Also added beyond the spec: checkpoint save/load (`config.checkpoint_path`) so `train.py` and `generate.py` share a trained model instead of each initializing a fresh random one.
