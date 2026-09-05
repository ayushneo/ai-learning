"""Hyperparameters for the nano-transformer.

Debug scale first, real scale once the pipeline is verified correct.
See nano-transformer-spec.md > Hyperparameters.
"""

import torch

# picks the fastest backend actually present: CUDA (Nvidia GPU) > MPS (Apple
# Silicon GPU) > CPU. Everything that allocates a tensor (data.py's batches,
# the model's parameters) must be moved here explicitly — PyTorch never
# does this for you, "having a GPU" isn't the same as "using the GPU".
device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

# verbose shape/data prints throughout the pipeline — cheap at debug scale,
# but printing full (batch_size, block_size) tensors thousands of times at
# real scale will dominate your wall-clock time. Flip on to inspect, off to train.
DEBUG = False

# --- debug scale: fast iteration, correctness first ---
# n_embd = 32
# n_head = 4
# n_layer = 2
# block_size = 8       # context length
# batch_size = 16
# dropout = 0.0         # keep 0 while debugging — dropout noise can mask real bugs

# --- "real" scale (needs a GPU) — swap in once debug scale trains correctly ---
n_embd = 384
n_head = 6
n_layer = 6
block_size = 256
batch_size = 64
dropout = 0.1        # 0.1-0.2

# --- training ---
learning_rate = 3e-4
max_iters = 5000
eval_interval = 500
eval_iters = 200      # batches averaged over in estimate_loss()

# --- misc ---
seed = 1337
data_path = "input.txt"
checkpoint_path = "checkpoint.pt"
