import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException

from dependencies import file_svc, render_svc, task_mgr
from docservice.baseclasses import DataRequest
from middlewares import verify_api_key
from queueworker import RenderJob, render_queue
from responsebuilder import ResponseBuilder

render_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
    tags=["Render"]
)

@render_router.post("/generate/{template_name}", summary="Render Data Synchronously")
async def generate_docx(template_name: str, req: DataRequest):
    res = await file_svc.prepare_generation(template_name, req)

    if res.is_hit:
        return ResponseBuilder.build_file_response_usePath(
            res.cache_path,
            req.expectName or template_name,
            res.data_hash,
            True)

    template_bytes = await file_svc.get_template_bytes(template_name)
    new_content = render_svc.render(template_bytes, req.data, req.images)
    file_svc.save_to_cache(res.cache_path, new_content)

    return ResponseBuilder.build_file_response(
        new_content,
        req.expectName or template_name,
        res.data_hash,
        False)

@render_router.post("/task/{template_name}", summary="Create a task of rendering a template")
async def create_render_task(template_name: str, req: DataRequest) -> str:
    task_id = uuid.uuid4()
    await task_mgr.create_task(task_id, template_name, req.expectName)
    try:
        render_queue.put_nowait(RenderJob(task_id, template_name, req))
        await file_svc.create_new_task_result_dir(task_id, template_name)
    except asyncio.QueueFull:
        await task_mgr.delete_task(task_id)
        raise HTTPException(status_code=429, detail="Server busy, please retry later")
    except Exception:
        await task_mgr.delete_task(task_id)
        raise
    return str(task_id)

@render_router.get("/task/file/{task_id}", summary="Download the rendered file of a task")
async def get_result_file(task_id: uuid.UUID):
    task = await task_mgr.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=task["error"] or "Task failed")
    if task["status"] != "done":
        raise HTTPException(status_code=425, detail=f"Task is {task['status']}, not ready yet")
    file_path = await file_svc.get_result_file_path(task_id)
    return ResponseBuilder.build_file_response_usePath(
        file_path,
        task["file_name"],
        task["data_hash"],
        True
    )