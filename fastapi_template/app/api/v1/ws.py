"""WebSocket echo endpoint -- exists to demonstrate two fastapi-tips, not as
a real feature. Delete alongside items.py if you don't need websockets.

# tip 3 (fastapi-tips/Kludex): iterate with `async for ... in websocket.iter_text()`
# instead of the commonly-copied `while True: await websocket.receive_text()`.
# Same behavior, no manual loop.
#
# tip 4: `async for` raises WebSocketDisconnect for you on client disconnect,
# so you only need to catch it, not check for it manually every iteration.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for message in websocket.iter_text():
            await websocket.send_text(f"echo: {message}")
    except WebSocketDisconnect:
        pass
