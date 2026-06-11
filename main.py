import datetime
import time

from fastapi import FastAPI, APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse

from docservice import settings
from docservice.baseclasses import DataRequest
from docservice.fileservice import FileService
from docservice.renderservice import RenderService
from docservice.templatestorage import build_template_storage
from logger import logger
from middlewares import universal_exception_handler, verify_api_key
from responsebuilder import ResponseBuilder
from settings import APP_NAME, APP_VERSION, APP_ENV

app = FastAPI(
    title=APP_NAME,
    description="Based on Docxtpl, providing automatic rendering of documents.",
    version=APP_VERSION,
    docs_url="/docs" if APP_ENV == "development" else None,)

app.add_exception_handler(Exception, universal_exception_handler)

template_storage = build_template_storage(settings)
file_svc = FileService(logger=logger, template_storage=template_storage, cache_dir=settings.CACHE_DIR)
render_svc = RenderService(image_fetch_timeout=settings.IMAGE_FETCH_TIMEOUT)

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

app.include_router(public_router)
app.include_router(protected_router)
