"""Pydantic schemas -- the request/response shape, kept separate from the
ORM model (app/models/item.py). Two classes that happen to look similar
today is cheaper than one class doing double duty: the DB row and the API
contract change for different reasons and at different times (a column
rename shouldn't have to be a versioned API change, and vice versa).
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets `.model_validate(orm_obj)` work directly

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
