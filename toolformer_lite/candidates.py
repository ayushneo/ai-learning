"""Heuristic candidate position generation (not the paper's own method).

Only consider inserting a Calculator call at positions where a number
appears in the text, since that's where a result is plausibly relevant.
"""


def find_candidate_positions(text: str, tokenizer) -> list[int]:
    # TODO: tokenize, then find token positions immediately after a numeric
    #       token (or, simpler: positions right before a sentence containing
    #       arithmetic-looking text)
    ...
