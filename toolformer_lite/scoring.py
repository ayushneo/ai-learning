"""L_i^+, L_i^-, the filtering criterion, and the weight function.

L_i(z) = -Sum_{j=i}^{n} w_{j-i} * log p_M(x_j | z, x_{1:j-1})
w_t = w~_t / Sum(w~_s), with w~_t = max(0, 1 - 0.2*t)
"""


def weight_fn(t: int, max_t: int = 5) -> float:
    # TODO: raw = max(0, 1 - 0.2 * t)
    # TODO: normalize by the sum of raw weights over t=0..max_t (raw is 0 past t=5 anyway)
    ...


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


def score_candidate(model, tokenizer, x, i, api_call, result) -> bool:
    tau_f = 1.0  # TODO: sweep this — see spec checkpoint 3

    prefix_with_result = linearize(api_call, result)  # e(c_i, r_i)
    prefix_call_only = linearize(api_call, None)       # e(c_i, epsilon)
    prefix_empty = ""                                   # epsilon

    target = x[i:]  # tokens after position i, up to the weighting window

    # TODO: L_plus  = compute_loss(model, tokenizer, prefix_with_result, target, weight_fn)
    # TODO: L_minus = min(
    #           compute_loss(model, tokenizer, prefix_empty, target, weight_fn),
    #           compute_loss(model, tokenizer, prefix_call_only, target, weight_fn),
    #       )
    # TODO: return (L_minus - L_plus) >= tau_f
    ...


def linearize(api_call, result) -> str:
    # TODO: render e.g. "[Calculator(3*4) -> 12]" if result is not None,
    #       else "[Calculator(3*4)]"
    ...
