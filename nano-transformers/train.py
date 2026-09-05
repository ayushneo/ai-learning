"""Training loop.

See nano-transformer-spec.md > Training loop / Debugging checkpoints.
"""

import math

import torch

import config
from data import get_batch, vocab_size
from model import NanoTransformer

torch.manual_seed(config.seed)
print(f"using device: {config.device}")

model = NanoTransformer(
    vocab_size=vocab_size,
    n_embd=config.n_embd,
    n_head=config.n_head,
    n_layer=config.n_layer,
    block_size=config.block_size,
    dropout=config.dropout,
).to(config.device)  # params must move to the same device as the batches from get_batch()
optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

if config.DEBUG:
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model: {n_params / 1e6:.2f}M params")


@torch.no_grad()
def estimate_loss():
    """Average loss over eval_iters batches, for both splits.

    A single batch is noisy enough to make a correctly-training model
    look broken — always report the averaged loss, not one batch's.
    """
    out = {}
    model.eval()
    for split in ("train", "val"):
        losses = torch.zeros(config.eval_iters)
        for i in range(config.eval_iters):
            xb, yb = get_batch(split)
            _, loss = model(xb, yb)
            losses[i] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


for iter in range(config.max_iters):
    xb, yb = get_batch("train")
    logits, loss = model(xb, yb)

    if iter == 0:
        # sanity checkpoint from the spec: with no training yet, the model is
        # guessing uniformly over the vocab, so loss should sit near
        # -ln(1/vocab_size). Far off -> bug in init or the loss computation,
        # not in learning dynamics.
        expected = -math.log(1 / vocab_size)
        print(f"initial loss {loss.item():.4f} (expected ~{expected:.4f} for vocab_size={vocab_size})")

    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

    if iter % config.eval_interval == 0:
        losses = estimate_loss()
        print(f"step {iter}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

torch.save(model.state_dict(), config.checkpoint_path)
print(f"saved checkpoint to {config.checkpoint_path}")

# Debugging checkpoints before trusting any of the above (see spec):
#  - overfit a tiny subset first, confirm loss -> ~0
#  - initial loss should be close to -ln(1/vocab_size) before training starts
#  - assert attention softmax rows sum to 1, causal mask upper triangle is 0
