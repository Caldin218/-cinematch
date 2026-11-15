from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse

class ApplicationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code, self.message, self.status_code = code, message, status_code


def install_handlers(app: FastAPI) -> None:
    def response(request: Request, code: str, message: str, status: int, details=None):
        return JSONResponse(status_code=status, content={"code": code, "message": message,
            "details": details, "request_id": getattr(request.state, "request_id", None)})

    @app.exception_handler(ApplicationError)
    async def application(request: Request, exc: ApplicationError):
        return response(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(HTTPException)
    async def http(request: Request, exc: HTTPException):
        result = response(request, f"http_{exc.status_code}", str(exc.detail), exc.status_code)
        if exc.headers:
            result.headers.update(exc.headers)
        return result

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        details = [{"field": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return response(request, "validation_error", "Request validation failed", 422, details)
