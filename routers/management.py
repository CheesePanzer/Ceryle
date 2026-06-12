from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dependencies import file_svc
from middlewares import require_admin

templates = Jinja2Templates(directory="mgt_templates")

mgt_protected_router = APIRouter(
    prefix="/management",
    tags=["Management"],
    dependencies=[Depends(require_admin)],
)

@mgt_protected_router.get("/", response_class=HTMLResponse)
async def management_dashboard(request: Request):
    tpl_list = await file_svc.list_templates()
    return templates.TemplateResponse(request, "management.html", {"templates": tpl_list, "message": None})


@mgt_protected_router.post("/templates/upload")
async def upload_template(
    request: Request,
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
):
    content = await file.read()
    message = ""
    try:
        saved_name = await file_svc.create_or_update_template(file.filename, content, overwrite=overwrite)
        message = f"Saved: {saved_name}"
        tpl_list = await file_svc.list_templates()
        return templates.TemplateResponse(
            request, "management.html",
            {"templates": tpl_list, "message": message}
        )
    except Exception as e:
        message = f"Failed to save template: {file.filename};\n Reason: {e};"
        tpl_list = await file_svc.list_templates()
        return templates.TemplateResponse(
            request, "management.html",
            {"templates": tpl_list, "error": message}
        )




@mgt_protected_router.post("/templates/{template_name}/delete")
async def delete_template(request: Request, template_name: str):
    await file_svc.delete_template(template_name)

    tpl_list = await file_svc.list_templates()
    return templates.TemplateResponse(
        request, "management.html",
        {"templates": tpl_list, "message": f"Deleted: {template_name}"}
    )


@mgt_protected_router.post("/cache/clear")
async def clear_cache(request: Request):
    count = file_svc.clear_all_cache()

    tpl_list = await file_svc.list_templates()
    return templates.TemplateResponse(
        request, "management.html",
        {"templates": tpl_list, "message": f"Cache cleared: {count} files removed"}
    )