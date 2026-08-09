# exception_handlers.py
from fastapi.security import APIKeyHeader
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import HTTPException, Security
from logger import logger
from docservice.exceptions import ServiceException
from settings import API_KEY


async def universal_exception_handler(request: Request, exc: Exception):
    status_code = 500
    title = "Internal Server Error"
    detail = str(exc)
    type_url = "about:blank"
    extensions = {}

    if isinstance(exc, ServiceException):
        status_code = exc.status_code
        title = "Service Error"
        detail = exc.message
        if exc.error_code:
            extensions["error_code"] = exc.error_code

    elif isinstance(exc, HTTPException):
        status_code = exc.status_code
        title = "HTTP Exception"
        detail = exc.detail
        if status_code == 404:
            title = "Not Found"

    logger.exception(f"{title}: {str(exc)}")

    problem_content = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }

    if extensions:
        problem_content.update(extensions)

    return JSONResponse(
        status_code=status_code,
        content=problem_content,
        media_type="application/problem+json"
    )


api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key not in API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

async def require_admin(request: Request):
    """
    Dependency for protected admin pages.
    Redirects to login if not authenticated.
    """
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})