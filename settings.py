APP_NAME:str = "Ceryle"

APP_VERSION:str = "1.0.0"

APP_ENV:str = "development"

API_KEY:str = "123456"

WORKER_COUNT: int = 1

PROCESS_POOL_SIZE: int = 4

TASK_QUEUE_SIZE: int = 50

CLEAN_CACHE_CRON: str = "0 3 * * *"

CLEAN_STUCK_PENDING: str = "*/10 * * * *"

CLEAN_STUCK_PROCESSING: str = "*/10 * * * *"

CLEAN_EXPIRED_FINISHED: str = "0 3 * * *"

SESSION_SECRET: str = "syh123456"

SESSION_MAX_AGE_SECS: int | None = None