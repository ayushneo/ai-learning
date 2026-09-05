"""Ties model + candidates + scoring together over a small text corpus."""
from toolformer_lite.candidates import find_candidate_positions
from toolformer_lite.model import load_model
from toolformer_lite.scoring import score_candidate
from toolformer_lite.tools import calculator


def run(corpus: list[str]):
    model, tokenizer = load_model()
    kept = []
    for text in corpus:
        # TODO: for each candidate position from find_candidate_positions(text, tokenizer):
        #   TODO: build an api_call string and run calculator() to get result
        #   TODO: if score_candidate(model, tokenizer, text, i, api_call, result): kept.append(...)
        ...
    return kept


if __name__ == "__main__":
    run(["A pair of shoes costs 3 * 4 = 12 dollars."])
