import asyncio
import shutil
import uuid
from typing import NamedTuple

from docservice import settings as docsettings
import settings
from docservice.baseclasses import DataRequest
from docservice.renderservice import RenderService
from renderprocesspool import process_pool


class RenderJob(NamedTuple):
    task_id: uuid.UUID
    template_name: str
    req: DataRequest


# Module-level queue - bounded, full -> 429 at submission time
render_queue: asyncio.Queue[RenderJob] = asyncio.Queue(maxsize=settings.TASK_QUEUE_SIZE)

def render_doc(template_bytes, data, images):

    svc = RenderService(image_fetch_timeout=docsettings.IMAGE_FETCH_TIMEOUT)

    return svc.render(
        template_bytes,
        data,
        images,
    )

async def worker(file_svc, render_svc, task_mgr, logger, task_dir: str = "result"):
    """
    Long-running consumer. Run N of these as background tasks (lifespan).
    """
    while True:
        job = await render_queue.get()
        try:
            await _process(job, file_svc, render_svc, task_mgr, task_dir, logger)
        except Exception as e:
            logger.exception(f"Task {job.task_id} failed: {e}")
            await task_mgr.fail_task(job.task_id, str(e))
        finally:
            render_queue.task_done()


async def _process(job: RenderJob, file_svc, render_svc, task_mgr, task_dir: str, logger):
    task_id, template_name, req = job

    await task_mgr.mark_running(task_id)

    res = await file_svc.prepare_generation(template_name, req)
    result_path = f"{task_dir}/{task_id}/result.docx"

    if res.is_hit:
        shutil.copy(res.cache_path, result_path)
        logger.info(f"Rendering {task_id}: Cache hit")
    else:
        template_bytes = await file_svc.get_template_bytes(template_name)

        loop = asyncio.get_running_loop()

        content = await loop.run_in_executor(
            process_pool,
            render_doc,
            template_bytes,
            req.data,
            req.images,
        )

        file_svc.save_to_cache(res.cache_path, content)
        shutil.copy(res.cache_path, result_path)
        logger.info(f"Rendering {task_id}: New Render")

    await task_mgr.complete_task(task_id, res.data_hash)