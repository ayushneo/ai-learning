"""FastAPI app + tool endpoints. Run: uvicorn react_mcp_server.main:app --reload"""
from fastapi import FastAPI
from pydantic import BaseModel, Field

from react_mcp_server.mcp_setup import mount_mcp
from react_mcp_server.tools import calculator, search

app = FastAPI(title="ReAct Tools")


class CalculatorInput(BaseModel):
    expression: str = Field(..., description="A basic arithmetic expression, e.g. '12 * (4 + 1)'")


class CalculatorOutput(BaseModel):
    result: float


@app.post("/calculator", operation_id="calculator", response_model=CalculatorOutput)
async def calculator_endpoint(input: CalculatorInput) -> CalculatorOutput:
    # TODO: call calculator(input.expression), cast to float
    ...


class SearchInput(BaseModel):
    query: str = Field(..., description="A search query, e.g. a factual question")


class SearchOutput(BaseModel):
    snippet: str


@app.post("/search", operation_id="search", response_model=SearchOutput)
async def search_endpoint(input: SearchInput) -> SearchOutput:
    # TODO: call search(input.query)
    ...


mount_mcp(app)
