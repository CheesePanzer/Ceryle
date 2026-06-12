import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

import settings
from docservice.cronjobs import (
    cleanup_cache_job,
    cleanup_stuck_queue_job,
    cleanup_stuck_processing_job,
    cleanup_expired_results_job,
)
from logger import logger
from middlewares import universal_exception_handler
from queueworker import worker
from routers.adminauth import admin_auth_router
from routers.management import mgt_protected_router
from routers.render import protected_router
from routers.system import public_router
from settings import APP_NAME, APP_VERSION, APP_ENV
from settings import WORKER_COUNT, CLEAN_CACHE_CRON, CLEAN_STUCK_PENDING, CLEAN_STUCK_PROCESSING, CLEAN_EXPIRED_FINISHED
from dependencies import file_svc, task_mgr, render_svc, admin_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    await task_mgr.init()
    await admin_auth.init()
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

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)

app.add_exception_handler(Exception, universal_exception_handler)

app.include_router(public_router)
app.include_router(protected_router)

app.include_router(admin_auth_router)

app.include_router(mgt_protected_router)
