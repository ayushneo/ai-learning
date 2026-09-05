"""The ReAct few-shot prompt template."""

TEMPLATE = """Answer the following question as best you can. You have access to the following tools:

{tool_descriptions}

Use this format:
Thought: reason about what to do next
Action: the tool to use, one of [{tool_names}]
Action Input: the input to the tool
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Question: What is 12 * (4 + 1)?
Thought: I need to compute this arithmetic expression.
Action: Calculator
Action Input: 12 * (4 + 1)
Observation: 60
Thought: I now know the final answer
Final Answer: 60

Question: What year was the Eiffel Tower completed?
Thought: I should search for this fact.
Action: Search
Action Input: Eiffel Tower completion year
Observation: The Eiffel Tower was completed in 1889.
Thought: I now know the final answer
Final Answer: 1889

Question: {question}"""

TOOL_DESCRIPTIONS = {
    "Calculator": "evaluates a basic arithmetic expression, e.g. '12 * (4 + 1)'",
    "Search": "looks up a short factual snippet for a query, e.g. 'Eiffel Tower completion year'",
}


def build_initial_prompt(question: str, tools: dict) -> str:
    descriptions = "\n".join(f"{name}: {TOOL_DESCRIPTIONS.get(name, '')}" for name in tools)
    names = ", ".join(tools)
    return TEMPLATE.format(tool_descriptions=descriptions, tool_names=names, question=question)
