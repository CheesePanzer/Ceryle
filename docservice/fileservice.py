import json
import hashlib
import os
import uuid
from dataclasses import dataclass
from io import BytesIO
from logging import Logger
from typing import Optional, Union, BinaryIO, List

from docservice.baseclasses import DataRequest
from docservice.exceptions import SFileNotFoundError
from docservice.templatestorage import TemplateStorage


@dataclass
class GenerationResult:
    data_hash: str
    is_hit: bool
    cache_path: str
    content: Optional[Union[BytesIO, BinaryIO]] = None


class FileService:
    """
    Responsible for template storage (delegated to TemplateStorage backend),
    cache lookup/storage, and lifecycle management.
    Knows nothing about rendering internals.
    """

    def __init__(self, logger: Logger, template_storage: TemplateStorage, cache_dir="cache", result_dir="result"):
        self.template_storage = template_storage
        self.cache_dir = cache_dir
        self.result_dir = result_dir
        self.logger = logger
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.result_dir, exist_ok=True)

    async def _get_hash(self, tpl_name: str, req: DataRequest) -> str:
        template_fingerprint = await self.template_storage.get_fingerprint(tpl_name)
        payload = {
            "request": req.model_dump(),
            "finger_print": template_fingerprint
        }
        data_json = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(data_json.encode('utf-8')).hexdigest()

    async def prepare_generation(self, tpl_name: str, req: DataRequest) -> GenerationResult:
        """
        Before generation, calculate hash and check if cache exists.
        """
        data_hash = await self._get_hash(tpl_name, req)
        cache_path = os.path.join(self.cache_dir, f"{data_hash}.docx")
        is_hit = os.path.exists(cache_path)

        return GenerationResult(
            data_hash=data_hash,
            is_hit=is_hit,
            cache_path=cache_path
        )

    def save_to_cache(self, cache_path: str, content: BytesIO) -> None:
        with open(cache_path, "wb") as f:
            f.write(content.getvalue())

    async def get_template_bytes(self, tpl_name: str) -> bytes:
        """
        Fetch template content for rendering. Raises SFileNotFoundError if missing.
        """
        if not await self.template_storage.exists(tpl_name):
            raise SFileNotFoundError(tpl_name)
        return await self.template_storage.read(tpl_name)

    async def create_or_update_template(self, filename: str, content: bytes, overwrite: bool = False) -> str:
        """
        Save or create a new template by filename.
        """
        return await self.template_storage.write(filename, content, overwrite=overwrite)

    async def delete_template(self, template_name: str) -> None:
        """
        Delete a template by name.
        """
        await self.template_storage.delete(template_name)

    async def list_templates(self) -> List[str]:
        """
        List all templates.
        """
        return await self.template_storage.list()

    def clear_all_cache(self) -> int:
        """
        Clean all cache, e.g. after a template is updated.
        """
        count = 0
        if not os.path.exists(self.cache_dir):
            return 0

        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            except Exception as e:
                self.logger.error(f"Failed to delete {filename}: {e}")
        return count

    async def create_new_task_result_dir(self, task_id:uuid.UUID, tpl_name: str) -> None:
        if not await self.template_storage.exists(tpl_name):
            raise SFileNotFoundError(tpl_name)
        os.makedirs(os.path.join(self.result_dir, str(task_id)))

    async def get_result_file_path(self, task_id: uuid.UUID) -> str:
        """
        Return the path to the rendered result file for a task.
        Raises SFileNotFoundError if the file doesn't exist (e.g. task not done yet).
        """
        path = os.path.join(self.result_dir, str(task_id), "result.docx")
        if not os.path.exists(path):
            raise SFileNotFoundError(str(task_id))
        return path