import logging
from contextvars import ContextVar
from uuid import UUID, uuid4
from starlette.responses import JSONResponse

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

class CorrelationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            identifier = str(UUID(headers.get(b"x-request-id", b"").decode("ascii")))
        except (ValueError, UnicodeError):
            identifier = str(uuid4())
        scope.setdefault("state", {})["request_id"] = identifier
        token = request_id.set(identifier)
        started = False
        async def correlated_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [(k,v) for k,v in message.get("headers", []) if k.lower() != b"x-request-id"]
                message["headers"].append((b"x-request-id", identifier.encode()))
                logging.getLogger("app.requests").info("request_completed", extra={"status_code": message["status"]})
            await send(message)
        try:
            await self.app(scope, receive, correlated_send)
        except Exception:
            logging.getLogger("app.requests").error("unhandled_request_error")
            if started:
                raise
            response = JSONResponse(status_code=500, content={"code":"internal_error",
                "message":"Internal server error", "details":None, "request_id":identifier})
            await response(scope, receive, correlated_send)
        finally:
            request_id.reset(token)
