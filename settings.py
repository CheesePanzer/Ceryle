import os

APP_NAME: str = os.getenv("APP_NAME", "Ceryle")

APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")

APP_ENV: str = os.getenv("APP_ENV", "development")

API_KEY: str = os.getenv("API_KEY", "123456")

WORKER_COUNT: int = int(os.getenv("WORKER_COUNT", "1"))

PROCESS_POOL_SIZE: int = int(os.getenv("PROCESS_POOL_SIZE", "4"))

TASK_QUEUE_SIZE: int = int(os.getenv("TASK_QUEUE_SIZE", "50"))

CLEAN_CACHE_CRON: str = os.getenv("CLEAN_CACHE_CRON", "0 3 * * *")

CLEAN_STUCK_PENDING: str = os.getenv("CLEAN_STUCK_PENDING", "*/10 * * * *")

CLEAN_STUCK_PROCESSING: str = os.getenv("CLEAN_STUCK_PROCESSING", "*/10 * * * *")

CLEAN_EXPIRED_FINISHED: str = os.getenv("CLEAN_EXPIRED_FINISHED", "0 3 * * *")

SESSION_SECRET: str = os.getenv("SESSION_SECRET", "123456")

SESSION_MAX_AGE_SECS: int | None = (
    int(os.environ["SESSION_MAX_AGE_SECS"])
    if os.getenv("SESSION_MAX_AGE_SECS") is not None
    else None
)