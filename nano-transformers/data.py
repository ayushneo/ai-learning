"""Char-level tokenizer + batching.

See nano-transformer-spec.md > Data & tokenizer.
"""

import torch

import config

with open(config.data_path, "r", encoding="utf-8") as f:
    text = f.read()

chars = sorted(set(text))
vocab_size = len(chars)

stoi = {ch: i for i, ch in enumerate(chars)}
itos = {i: ch for i, ch in enumerate(chars)}


def encode(s: str) -> list[int]:
    return [stoi[c] for c in s]


def decode(tokens: list[int]) -> str:
    return "".join(itos[i] for i in tokens)


data = torch.tensor(encode(text), dtype=torch.long)
if config.DEBUG:
    print(f"data.py: {len(data)} tokens, vocab_size={vocab_size}")

n = int(0.9 * len(data))
train_data = data[:n]
val_data = data[n:]

# real bug this catches: block_size bigger than a split's length makes
# torch.randint's range go negative (e.g. len=61, block_size=256 -> high=-195),
# which raises a cryptic "from=0 >= to=-195" deep inside torch. Fail loudly
# here instead, naming the split and the actual sizes involved.
for _split_name, _split_data in (("train", train_data), ("val", val_data)):
    assert len(_split_data) > config.block_size, (
        f"{_split_name} split has {len(_split_data)} tokens, "
        f"too short for block_size={config.block_size}. "
        "Shrink block_size or use a longer input.txt."
    )


def get_batch(split: str):
    """Sample a random batch of (x, y) windows.

    x, y shape: (batch_size, block_size). y is x shifted by one position —
    the next-token target for every position in x.
    """
    data_split = train_data if split == "train" else val_data
    ix = torch.randint(len(data_split) - config.block_size, (config.batch_size,))
    x = torch.stack([data_split[i:i + config.block_size] for i in ix])
    y = torch.stack([data_split[i + 1:i + config.block_size + 1] for i in ix])
    # move the batch to the training device — the model lives there (see train.py),
    # and PyTorch errors if you feed it a CPU tensor while it's on cuda/mps.
    x, y = x.to(config.device), y.to(config.device)
    if config.DEBUG:
        print(f"get_batch({split}): x{tuple(x.shape)} y{tuple(y.shape)}")
    return x, y
