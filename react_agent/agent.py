"""The ReAct agent loop. Run: python -m react_agent.agent "your question"."""
import sys

from react_agent.parser import parse_llm_output
from react_agent.prompt import build_initial_prompt
from react_agent.tools import TOOLS


def run_agent(question: str, tools: dict = TOOLS, llm=None, max_iters: int = 6) -> str:
    if llm is None:
        from react_agent.llm import complete as llm

    transcript = build_initial_prompt(question, tools)
    for _ in range(max_iters):
        output = llm(transcript, stop=["Observation:"])
        transcript += output
        result = parse_llm_output(output)

        if result["type"] == "final":
            return result["answer"]

        if result["type"] == "action":
            name, tool_input = result["name"], result["input"]
            if name not in tools:
                observation = f"error: unknown tool '{name}'"
            else:
                observation = tools[name](tool_input)
            transcript += f"\nObservation: {observation}\n"
            continue

        # parse_error: nudge once instead of silently proceeding
        transcript += (
            "\nObservation: parse error — your last message didn't match the "
            "Thought/Action/Action Input or Final Answer format. Try again.\n"
        )

    return f"gave up after {max_iters} steps without a Final Answer"


def demo():
    # Fake LLM: two tool calls then a final answer, no network needed.
    scripted = iter([
        "Thought: need to add\nAction: Calculator\nAction Input: 2 + 2\n",
        "Thought: need to search\nAction: Search\nAction Input: ignored\n",
        "Thought: done\nFinal Answer: 4 and a snippet",
    ])
    fake_tools = {"Calculator": lambda x: "4", "Search": lambda x: "a snippet"}
    fake_llm = lambda transcript, stop=None: next(scripted)
    answer = run_agent("dummy question", tools=fake_tools, llm=fake_llm)
    assert answer == "4 and a snippet", answer

    # parse_error path: garbage output should not silently pass through
    bad_then_final = iter(["not in the expected format at all", "Final Answer: recovered"])
    fake_llm2 = lambda transcript, stop=None: next(bad_then_final)
    answer2 = run_agent("dummy", tools=fake_tools, llm=fake_llm2)
    assert answer2 == "recovered", answer2
    print("agent.py: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        question = " ".join(sys.argv[1:]) or "What is 12 * (4 + 1)?"
        print(run_agent(question))
