IMAGE_FETCH_TIMEOUT: int = 2
# "local" or "s3"
STORAGE_BACKEND: str = "local"
# Local backend
TEMPLATE_DIR: str = "templates"
CACHE_DIR: str = "cache"
# S3 backend (only required if STORAGE_BACKEND == "s3")
S3_BUCKET: str = ""
S3_REGION: str = "ap-southeast-2"
S3_TEMPLATE_PREFIX: str = "templates/"
# Optional: for S3-compatible services (MinIO, etc). Leave unset for AWS.
S3_ENDPOINT_URL: str | None = None
