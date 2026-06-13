import shutil

from fastapi import APIRouter, Form, Depends, UploadFile, File
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

import settings
from decorators import render_errors, get_flashes, flash, flash_errors
from dependencies import admin_auth, file_svc, task_mgr
from docservice.settings import STUCK_QUEUE_SECS, STUCK_PROCESSING_SECS, RESULT_EXPIRY_SECS
from middlewares import require_admin
from queueworker import render_queue
from docservice import settings as docservice_settings

admin_auth_router = APIRouter(prefix="/admin", tags=["Admin"], include_in_schema=False)

templates = Jinja2Templates(directory="admin_templates")

@admin_auth_router.get("/login", response_class=HTMLResponse)
@render_errors
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(request,"login.html", {"request": request, "error": None})

@admin_auth_router.post("/login")
@render_errors
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

    return RedirectResponse("/admin", status_code=302)

@admin_auth_router.get("/logout")
@render_errors
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)

@admin_auth_router.get("/change-password", response_class=HTMLResponse)
@render_errors
async def change_password_page(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/admin/login", status_code=302)
    return templates.TemplateResponse(request,
        "change_password.html",
        {"request": request, "error": None, "forced": await admin_auth.must_change_password()}
    )

@admin_auth_router.post("/change-password")
@render_errors
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
    return RedirectResponse("/admin", status_code=302)


mgt_protected_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
    include_in_schema=False
)


@mgt_protected_router.get("/", response_class=HTMLResponse)
@render_errors
async def management_dashboard(request: Request):
    config_payload = {
        "APP_NAME": settings.APP_NAME,
        "APP_VERSION": settings.APP_VERSION,
        "APP_ENV": settings.APP_ENV,
        "TASK_QUEUE_SIZE": settings.TASK_QUEUE_SIZE,
        "STORAGE_BACKEND": docservice_settings.STORAGE_BACKEND,
        "S3_REGION": docservice_settings.S3_REGION,
        "CLEAN_CACHE_CRON": settings.CLEAN_CACHE_CRON,
        "CLEAN_STUCK_PENDING": settings.CLEAN_STUCK_PENDING,
        "CLEAN_STUCK_PROCESSING": settings.CLEAN_STUCK_PROCESSING,
        "CLEAN_EXPIRED_FINISHED": settings.CLEAN_EXPIRED_FINISHED,
        "STUCK_QUEUE_SECS": docservice_settings.STUCK_QUEUE_SECS,
        "RESULT_EXPIRY_SECS": docservice_settings.RESULT_EXPIRY_SECS,
    }
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "config": config_payload,
            "flashes": get_flashes(request)
        })

@mgt_protected_router.post("/cache/clear")
@flash_errors("/admin")
async def clear_cache(request: Request):
    count = file_svc.clear_all_cache()
    flash(request, f"Cache Cleared: {count} Records")
    return RedirectResponse("/admin", status_code=303)

@mgt_protected_router.post("/jobs/cleanup-stuck-queue")
@flash_errors("/admin")
async def run_cleanup_stuck_queue(request: Request):
    stuck_ids = await task_mgr.get_stuck_in_queue_task_ids(STUCK_QUEUE_SECS)
    for tid in stuck_ids:
        await task_mgr.fail_task(tid, "Task timed out in queue")
    flash(request, f"Marked {len(stuck_ids)} stuck-in-queue tasks as failed")
    return RedirectResponse("/admin", status_code=303)


@mgt_protected_router.post("/jobs/cleanup-stuck-processing")
@flash_errors("/admin")
async def run_cleanup_stuck_processing(request: Request):
    stuck_ids = await task_mgr.get_stuck_processing_task_ids(STUCK_PROCESSING_SECS)
    for tid in stuck_ids:
        await task_mgr.fail_task(tid, "Task timed out while processing")
        shutil.rmtree(f"{file_svc.result_dir}/{tid}", ignore_errors=True)
    flash(request, f"Marked {len(stuck_ids)} stuck-processing tasks as failed")
    return RedirectResponse("/admin", status_code=303)


@mgt_protected_router.post("/jobs/cleanup-expired-results")
@flash_errors("/admin")
async def run_cleanup_expired_results(request: Request):
    expired_ids = await task_mgr.get_expired_finished_task_ids(RESULT_EXPIRY_SECS)
    for tid in expired_ids:
        shutil.rmtree(f"{file_svc.result_dir}/{tid}", ignore_errors=True)
        await task_mgr.delete_task(tid)
    flash(request, f"Cleaned up {len(expired_ids)} expired tasks")
    return RedirectResponse("/admin", status_code=303)\

@mgt_protected_router.get("/status")
async def queue_status():

    task_status = await task_mgr.get_task_status()

    return \
        {
        "queue_size": render_queue.qsize(),
        "max_size": render_queue.maxsize,
        "workers": settings.WORKER_COUNT,
        "task_status": task_status,
        }

@mgt_protected_router.get("/templates", response_class=HTMLResponse)
@render_errors
async def management_templates(request: Request):
    tpl_list = await file_svc.list_templates()
    return templates.TemplateResponse(
        request,
        "templates.html",
        {
            "templates": tpl_list,
            "flashes": get_flashes(request)
        })

@mgt_protected_router.post("/templates/upload")
@flash_errors("/admin/templates")
async def upload_template(
        request: Request,
        file: UploadFile = File(...),
        overwrite: bool = Form(False),
):
    content = await file.read()
    saved_name = await file_svc.create_or_update_template(file.filename, content, overwrite=overwrite)
    flash(request, f"Saved: {saved_name}")
    return RedirectResponse("/admin/templates", status_code=303)


@mgt_protected_router.post("/templates/{template_name}/delete")
@flash_errors("/admin/templates")
async def delete_template(request: Request, template_name: str):
    await file_svc.delete_template(template_name)
    flash(request, f"Deleted: {template_name}")
    return RedirectResponse("/admin/templates", status_code=303)

@mgt_protected_router.get("/templates/{template_name}/download")
@flash_errors("/admin/templates")
async def download_template(request: Request, template_name: str):
    content = await file_svc.get_template_bytes(template_name)

    filename = template_name if template_name.endswith(".docx") else f"{template_name}.docx"

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@mgt_protected_router.get("/tasks")
@render_errors
async def read_all_tasks_page(request: Request):
    all_tasks = await task_mgr.get_all_tasks()
    return templates.TemplateResponse(
        request,
        "tasks.html",
        {"request": request, "tasks": all_tasks, "flashes": []}
    )
