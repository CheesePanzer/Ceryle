import os

from fastapi import APIRouter, Form, UploadFile, File, Depends

from dependencies import file_svc
from docservice.exceptions import SFileTypeError
from middlewares import verify_api_key

management_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
    tags=["Management"]
)

@management_router.get("/templates", summary="Get Current Templates List")
async def management_templates():
    tpl_list = await file_svc.list_templates()
    return tpl_list

@management_router.post("/templates/upload", summary="Upload Template")
async def upload_template(file: UploadFile = File(...),overwrite: bool = Form(False)):
    name, ext = os.path.splitext(file.filename)
    if ext != ".docx":
        raise SFileTypeError(name)
    content = await file.read()
    saved_name = await file_svc.create_or_update_template(file.filename, content, overwrite=overwrite)
    return f"Successfully Saved Template {saved_name}"


@management_router.post("/templates/{template_name}/delete", summary="Delete A Template")
async def delete_template(template_name: str):
    await file_svc.delete_template(template_name)
    return f"Successfully Deleted Template {template_name}"