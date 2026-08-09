from admin.authservice import AdminAuthManager
from docservice import settings
from docservice.fileservice import FileService
from docservice.renderservice import RenderService
from docservice.taskmanager import TaskManager
from docservice.templatestorage import build_template_storage
from logger import logger

template_storage = build_template_storage(settings)
file_svc = FileService(logger=logger, template_storage=template_storage, cache_dir=settings.CACHE_DIR)
render_svc = RenderService(image_fetch_timeout=settings.IMAGE_FETCH_TIMEOUT)
task_mgr = TaskManager(db_path="data.db")
admin_auth = AdminAuthManager(db_path="data.db")