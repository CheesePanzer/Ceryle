import os
from typing import List, Protocol, runtime_checkable

import aioboto3

from docservice.exceptions import SFileNotFoundError, SFileInvalidOperationError


@runtime_checkable
class TemplateStorage(Protocol):
    """
    Common interface for template storage backends.
    All methods are async to support both local (wrapped) and S3 (native async) implementations.
    """

    async def exists(self, name: str) -> bool: ...

    async def read(self, name: str) -> bytes: ...

    async def write(self, name: str, content: bytes, overwrite: bool = False) -> str: ...

    async def delete(self, name: str) -> None: ...

    async def list(self) -> List[str]: ...

    async def get_fingerprint(self, name: str) -> str: ...


def _normalize_name(name: str) -> str:
    """Ensure name has .docx extension and strip any path components."""
    base = os.path.basename(name)
    if not base.endswith(".docx"):
        base += ".docx"
    return base


class LocalTemplateStorage:
    """
    Filesystem-backed template storage.
    """

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir
        os.makedirs(self.template_dir, exist_ok=True)

    def _path(self, name: str) -> str:
        return os.path.join(self.template_dir, _normalize_name(name))

    async def exists(self, name: str) -> bool:
        return os.path.exists(self._path(name))

    async def read(self, name: str) -> bytes:
        path = self._path(name)
        if not os.path.exists(path):
            raise SFileNotFoundError(name)
        with open(path, "rb") as f:
            return f.read()

    async def write(self, name: str, content: bytes, overwrite: bool = False) -> str:
        clean_name = _normalize_name(name)
        path = self._path(clean_name)

        if os.path.exists(path) and not overwrite:
            raise SFileInvalidOperationError(clean_name, "overwrite")

        with open(path, "wb") as f:
            f.write(content)

        return clean_name

    async def delete(self, name: str) -> None:
        path = self._path(name)
        if not os.path.exists(path):
            raise SFileNotFoundError(name)
        os.remove(path)

    async def list(self) -> List[str]:
        return [f for f in os.listdir(self.template_dir) if f.endswith(".docx")]

    async def get_fingerprint(self, name: str) -> str:
        path = self._path(name)
        if not os.path.exists(path):
            raise SFileNotFoundError(name)
        stat = os.stat(path)
        return f"{stat.st_mtime}_{stat.st_size}"


class S3TemplateStorage:
    """
    S3-backed template storage using aioboto3.
    Enables sharing templates across multiple nodes.
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        prefix: str = "templates/",
        endpoint_url: str | None = None,
    ):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.endpoint_url = endpoint_url
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
        )

    def _key(self, name: str) -> str:
        return f"{self.prefix}{_normalize_name(name)}"

    async def exists(self, name: str) -> bool:
        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=self._key(name))
                return True
            except s3.exceptions.ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
                raise

    async def read(self, name: str) -> bytes:
        async with self._client() as s3:
            try:
                resp = await s3.get_object(Bucket=self.bucket, Key=self._key(name))
            except s3.exceptions.NoSuchKey:
                raise SFileNotFoundError(name)
            async with resp["Body"] as stream:
                return await stream.read()

    async def write(self, name: str, content: bytes, overwrite: bool = False) -> str:
        clean_name = _normalize_name(name)

        if not overwrite and await self.exists(clean_name):
            raise SFileInvalidOperationError(clean_name, "overwrite")

        async with self._client() as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=self._key(clean_name),
                Body=content,
                ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        return clean_name

    async def delete(self, name: str) -> None:
        if not await self.exists(name):
            raise SFileNotFoundError(name)
        async with self._client() as s3:
            await s3.delete_object(Bucket=self.bucket, Key=self._key(name))

    async def list(self) -> List[str]:
        results: List[str] = []
        async with self._client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".docx"):
                        results.append(os.path.basename(key))
        return results

    async def get_fingerprint(self, name: str) -> str:
        async with self._client() as s3:
            try:
                resp = await s3.head_object(Bucket=self.bucket, Key=self._key(name))
            except s3.exceptions.ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    raise SFileNotFoundError(name)
                raise
            # ETag is quoted, strip quotes; combine with size for stability
            etag = resp["ETag"].strip('"')
            size = resp["ContentLength"]
            return f"{etag}_{size}"


def build_template_storage(settings) -> TemplateStorage:
    """
    Factory: build the configured storage backend from settings.
    """
    if settings.STORAGE_BACKEND == "s3":
        return S3TemplateStorage(
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            prefix=settings.S3_TEMPLATE_PREFIX,
            endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
        )
    return LocalTemplateStorage(template_dir=settings.TEMPLATE_DIR)