"""Tool implementations for the hand-rolled ReAct agent.

Calculator uses eval() on a restricted namespace — fine for a local, personal
toy that never takes input from anyone else. Don't carry that pattern into
anything that does.
"""
import math

_SAFE_NAMES = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}


def calculator(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, _SAFE_NAMES)
    except Exception as e:
        return f"error: {e}"
    return str(result)


def search(query: str) -> str:
    try:
        import wikipedia
    except ImportError:
        return "error: `wikipedia` package not installed (pip install wikipedia)"
    try:
        return wikipedia.summary(query, sentences=2, auto_suggest=True)
    except Exception as e:
        return f"error: {e}"


TOOLS = {
    "Calculator": calculator,
    "Search": search,
}


def demo():
    assert calculator("2 + 2") == "4"
    assert calculator("sqrt(16)") == "4.0"
    assert "error" in calculator("__import__('os')")
    print("tools.py: ok")


if __name__ == "__main__":
    demo()
