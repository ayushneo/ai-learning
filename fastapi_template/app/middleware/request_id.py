"""Request-ID middleware, as a pure ASGI middleware.

# tip 8 (fastapi-tips/Kludex): implement pure ASGI middleware instead of
# BaseHTTPMiddleware (what `@app.middleware("http")` wraps). BaseHTTPMiddleware
# has a real perf penalty (buffers the response, breaks streaming responses
# in older Starlette versions) because it adapts the ASGI interface to a
# request/response one internally. A pure ASGI middleware talks the protocol
# directly -- more boilerplate (the scope/receive/send dance below), no
# per-request overhead. Worth it for something on the hot path of every
# request, like this one; use BaseHTTPMiddleware for anything low-traffic
# where readability wins over the last microseconds.
"""
import logging
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

HEADER_NAME = b"x-request-id"


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers", [])).get(HEADER_NAME)
        request_id = incoming.decode() if incoming else str(uuid.uuid4())

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((HEADER_NAME, request_id.encode()))
            await send(message)

        logger.info("request started", extra={"request_id": request_id})
        await self.app(scope, receive, send_with_header)
