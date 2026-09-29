"""Declarative base for all ORM models. One base = one metadata = one set of
tables Alembic can autogenerate migrations from (`Base.metadata` in
migrations/env.py). Don't create a second Base -- Alembic would only see
whichever one env.py imports.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
