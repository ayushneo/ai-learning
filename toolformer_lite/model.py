"""Load a HuggingFace model + tokenizer. Needs real token log-probs, so a local
open-weight model — GPT-2-small or Pythia-160m/410m — not a hosted API.
"""


def load_model(name: str = "gpt2"):
    # TODO: from transformers import AutoModelForCausalLM, AutoTokenizer
    # TODO: tokenizer = AutoTokenizer.from_pretrained(name)
    # TODO: model = AutoModelForCausalLM.from_pretrained(name)
    # TODO: model.eval()
    # TODO: return model, tokenizer
    ...
