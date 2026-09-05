"""Sample text from a trained model.

See nano-transformer-spec.md > Full model > generate().
"""

import os

import torch

import config
from data import decode, vocab_size
from model import NanoTransformer

model = NanoTransformer(
    vocab_size=vocab_size,
    n_embd=config.n_embd,
    n_head=config.n_head,
    n_layer=config.n_layer,
    block_size=config.block_size,
    dropout=config.dropout,
).to(config.device)

if os.path.exists(config.checkpoint_path):
    # map_location handles training on one device (e.g. a cuda box) and
    # generating on another (e.g. this laptop's cpu/mps) — without it,
    # loading a cuda checkpoint on a machine with no GPU raises an error.
    try:
        model.load_state_dict(torch.load(config.checkpoint_path, map_location=config.device))
    except RuntimeError as e:
        # the likely cause: config.py's hyperparameters changed since this
        # checkpoint was trained (e.g. debug scale -> real scale), so the
        # saved tensor shapes no longer match this model's architecture.
        raise RuntimeError(
            f"failed to load {config.checkpoint_path} — likely a config.py mismatch "
            "with the run that trained it (n_embd/n_head/n_layer/block_size). "
            "Retrain with the current config, or restore the config used to train it."
        ) from e
else:
    print(f"no checkpoint at {config.checkpoint_path} — sampling from a randomly-initialized model")

model.eval()

# start generation from a single "newline" token (or any valid token id)
context = torch.zeros((1, 1), dtype=torch.long, device=config.device)
out = model.generate(context, max_new_tokens=500)
print(decode(out[0].tolist()))

# Early in training this should look close to random characters —
# suspiciously clean output right away means a bug (e.g. copying input), not a good sign.
