import time
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse
from logger import logger
from settings import APP_NAME, APP_VERSION

public_router = APIRouter(tags=["System"])

@public_router.get("/", include_in_schema=False)
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
        "datetime": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "service": APP_NAME,
        "version": APP_VERSION,
    }