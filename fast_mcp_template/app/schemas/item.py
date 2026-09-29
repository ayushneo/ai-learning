"""Pydantic schemas -- the request/response shape, kept separate from the
ORM model (app/models/item.py). Two classes that happen to look similar
today is cheaper than one class doing double duty: the DB row and the API
contract change for different reasons and at different times (a column
rename shouldn't have to be a versioned API change, and vice versa).

Field(..., description=...) below is not decoration. fastapi_mcp turns each
field's description into part of the tool schema an MCP client (an LLM) sees
when deciding whether and how to call the tool -- write these for that
reader, the same way you'd write a docstring for a person you can't ask
questions.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str = Field(..., description="Short human-readable name for the item, e.g. 'blue widget'.")
    description: str | None = Field(None, description="Optional longer free-text description of the item.")


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets `.model_validate(orm_obj)` work directly

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
