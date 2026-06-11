import shutil

from docservice.settings import STUCK_QUEUE_SECS, STUCK_PROCESSING_SECS, RESULT_EXPIRY_SECS


def cleanup_cache_job(file_svc, logger):
    """
    Remove all cached rendered files. Cache is fully derivable from
    template + data, safe to clear unconditionally.
    """
    count = file_svc.clear_all_cache()
    logger.info(f"Cache cleanup: removed {count} files")


async def cleanup_stuck_queue_job(task_mgr, logger):
    """
    Tasks that sat in 'pending' too long without ever being picked up.
    No result directory expected (created just before enqueue), but
    cleanup is left to cleanup_expired_results_job once marked failed.
    """
    stuck_ids = await task_mgr.get_stuck_in_queue_task_ids(STUCK_QUEUE_SECS)
    for tid in stuck_ids:
        await task_mgr.fail_task(tid, "Task timed out in queue")

    if stuck_ids:
        logger.warning(f"Marked {len(stuck_ids)} stuck-in-queue tasks as failed")


async def cleanup_stuck_processing_job(file_svc, task_mgr, logger):
    """
    Tasks that started processing but never reached a terminal state
    (worker crashed mid-render). Mark failed and remove any partial output.
    """
    stuck_ids = await task_mgr.get_stuck_processing_task_ids(STUCK_PROCESSING_SECS)
    for tid in stuck_ids:
        await task_mgr.fail_task(tid, "Task timed out while processing")
        shutil.rmtree(f"{file_svc.result_dir}/{tid}", ignore_errors=True)

    if stuck_ids:
        logger.warning(f"Marked {len(stuck_ids)} stuck-processing tasks as failed")


async def cleanup_expired_results_job(file_svc, task_mgr, logger):
    """
    Tasks that reached a terminal state (done/failed) past their result TTL.
    Remove result directory and DB row entirely.
    """
    expired_ids = await task_mgr.get_expired_finished_task_ids(RESULT_EXPIRY_SECS)
    for tid in expired_ids:
        shutil.rmtree(f"{file_svc.result_dir}/{tid}", ignore_errors=True)
        await task_mgr.delete_task(tid)

    if expired_ids:
        logger.info(f"Cleaned up {len(expired_ids)} expired tasks")