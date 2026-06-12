import os
import sys
import logging

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler

import settings

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

time_handler = ConcurrentTimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "app.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8"
)

time_handler.suffix = "%Y-%m-%d"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(name)s - %(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        time_handler
    ]
)

logger = logging.getLogger(f"{settings.APP_NAME}_Logger")