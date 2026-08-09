# decorators.py 或单独 flash.py
import functools

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates

from docservice.exceptions import ServiceException


def flash(request: Request, message: str, category: str = "message"):
    request.session.setdefault("_flashes", []).append({"category": category, "text": message})


def get_flashes(request: Request) -> list[dict]:
    return request.session.pop("_flashes", [])


def flash_errors(redirect_to: str = "/admin"):
    """
    For POST-then-redirect handlers. On exception, push the error message
    into the flash queue and redirect (instead of rendering error.html).
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None
            )

            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if isinstance(exc, ServiceException):
                    detail = exc.message
                elif isinstance(exc, HTTPException):
                    detail = str(exc.detail)
                else:
                    detail = str(exc)

                if request:
                    flash(request, detail, category="error")

                return RedirectResponse(redirect_to, status_code=303)

        return wrapper

    return decorator


templates = Jinja2Templates(directory="admin_templates")


def render_errors(func):
    """
    Catch exceptions raised in an MVC-style route handler and render error.html
    instead of letting them bubble up to the global JSON exception handler.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # request 可能在 args 或 kwargs 里，按 FastAPI 注入习惯找出来
        request: Request = kwargs.get("request") or next(
            (a for a in args if isinstance(a, Request)), None
        )

        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            title = "Internal Server Error"
            detail = str(exc)
            status_code = 500

            if isinstance(exc, ServiceException):
                status_code = exc.status_code
                title = "Service Error"
                detail = exc.message
            elif isinstance(exc, HTTPException):
                status_code = exc.status_code
                title = "Error"
                detail = exc.detail

            return templates.TemplateResponse(
                request, "error.html",
                {"title": title, "detail": detail, "back_url": "/admin"},
                status_code=status_code
            )

    return wrapper
