import asyncio
import datetime
import time
import uuid
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse
from docservice import settings
from docservice.baseclasses import DataRequest
from docservice.fileservice import FileService
from queueworker import worker, render_queue, RenderJob
from docservice.renderservice import RenderService
from settings import WORKER_COUNT, CLEAN_CACHE_CRON, CLEAN_STUCK_PENDING, CLEAN_STUCK_PROCESSING, CLEAN_EXPIRED_FINISHED
from docservice.taskmanager import TaskManager
from docservice.templatestorage import build_template_storage
from logger import logger
from middlewares import universal_exception_handler, verify_api_key
from responsebuilder import ResponseBuilder
from settings import APP_NAME, APP_VERSION, APP_ENV
from docservice.cronjobs import (
    cleanup_cache_job,
    cleanup_stuck_queue_job,
    cleanup_stuck_processing_job,
    cleanup_expired_results_job,
)

template_storage = build_template_storage(settings)
file_svc = FileService(logger=logger, template_storage=template_storage, cache_dir=settings.CACHE_DIR)
render_svc = RenderService(image_fetch_timeout=settings.IMAGE_FETCH_TIMEOUT)
task_mgr = TaskManager(db_path="tasks.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await task_mgr.init()
    workers = [
        asyncio.create_task(worker(file_svc, render_svc, task_mgr, logger))
        for _ in range(WORKER_COUNT)
    ]
    scheduler = BackgroundScheduler()

    scheduler.add_job(lambda: cleanup_cache_job(file_svc, logger),
                      CronTrigger.from_crontab(CLEAN_CACHE_CRON))

    scheduler.add_job(lambda: asyncio.create_task(cleanup_stuck_queue_job(task_mgr, logger)),
                      CronTrigger.from_crontab(CLEAN_STUCK_PENDING))

    scheduler.add_job(lambda: asyncio.create_task(cleanup_stuck_processing_job(file_svc, task_mgr, logger)),
                      CronTrigger.from_crontab(CLEAN_STUCK_PROCESSING))

    scheduler.add_job(lambda: asyncio.create_task(cleanup_expired_results_job(file_svc, task_mgr, logger)),
                      CronTrigger.from_crontab(CLEAN_EXPIRED_FINISHED))

    scheduler.start()
    yield
    for w in workers:
        w.cancel()
    scheduler.shutdown()

app = FastAPI(
    title=APP_NAME,
    lifespan=lifespan,
    description="Based on Docxtpl, providing automatic rendering of documents.",
    version=APP_VERSION,
    docs_url="/docs" if APP_ENV == "development" else None,)

app.add_exception_handler(Exception, universal_exception_handler)

public_router = APIRouter(tags=["System"])

protected_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
    tags=["Business"]
)

@public_router.get("/")
async def index():
    return RedirectResponse(url="/health")

class HealthResult(BaseModel):
    status: str = Field(..., description="Status")
    timestamp: float = Field(..., description="Unix timestamp")
    datetime: str = Field(..., description="Readable Time")
    service: str = Field(..., description="Service Name")
    version: str = Field(..., description="Service Version")

@public_router.get("/health", response_model=HealthResult, summary="Health Check Endpoint")
async def health_check():
    now = time.time()
    logger.debug(f"Health check performed for {APP_NAME}")

    return {
        "status": "Healthy",
        "timestamp": now,
        "datetime": datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "service": APP_NAME,
        "version": APP_VERSION,
    }

@protected_router.post("/generate/{template_name}", summary="To Render the Data into that template")
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

@protected_router.post("/task/{template_name}", summary="Create a task of rendering a template")
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

@protected_router.get("/task/file/{task_id}", summary="Download the rendered file for a task")
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

app.include_router(public_router)
app.include_router(protected_router)
