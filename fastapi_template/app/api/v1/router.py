"""Aggregates every v1 resource router into one include_router() call in
main.py. Adding a resource means one line here, not touching main.py again.
"""
from fastapi import APIRouter

from app.api.v1 import items, ws

router = APIRouter(prefix="/v1")
router.include_router(items.router)
router.include_router(ws.router)
