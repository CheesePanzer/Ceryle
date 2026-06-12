from fastapi import APIRouter, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from dependencies import admin_auth

admin_auth_router = APIRouter(prefix="/admin", tags=["Admin"])

templates = Jinja2Templates(directory="auth_templates")

@admin_auth_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/admin/login")

@admin_auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/management", status_code=302)
    return templates.TemplateResponse(request,"login.html", {"request": request, "error": None})


@admin_auth_router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not await admin_auth.verify(username, password):
        return templates.TemplateResponse(request,
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401
        )

    request.session["authenticated"] = True
    request.session["username"] = username

    if await admin_auth.must_change_password():
        return RedirectResponse("/admin/change-password", status_code=302)

    return RedirectResponse("/management", status_code=302)


@admin_auth_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


@admin_auth_router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/admin/login", status_code=302)
    return templates.TemplateResponse(request,
        "change_password.html",
        {"request": request, "error": None, "forced": await admin_auth.must_change_password()}
    )


@admin_auth_router.post("/change-password")
async def change_password(
        request: Request,
        new_username: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/admin/login", status_code=302)

    if new_password != confirm_password:
        return templates.TemplateResponse(request,
            "change_password.html",
            {"request": request, "error": "Passwords do not match",
             "forced": await admin_auth.must_change_password()},
            status_code=400
        )

    if len(new_password) < 8:
        return templates.TemplateResponse(request,
            "change_password.html",
            {"request": request, "error": "Password must be at least 8 characters",
             "forced": await admin_auth.must_change_password()},
            status_code=400
        )

    await admin_auth.change_password(new_username, new_password)
    request.session["username"] = new_username
    return RedirectResponse("/management", status_code=302)