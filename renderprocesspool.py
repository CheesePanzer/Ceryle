from concurrent.futures import ProcessPoolExecutor

import settings

process_pool = ProcessPoolExecutor(max_workers=settings.PROCESS_POOL_SIZE)