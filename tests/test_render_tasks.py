import asyncio
import uuid

import pytest
from fastapi import HTTPException

from docservice.baseclasses import DataRequest
from routers import render


class TaskManagerStub:
    def __init__(self, events):
        self.events = events
        self.created = None
        self.deleted = []

    async def create_task(self, task_id, template_name, file_name):
        self.events.append("create_task")
        self.created = (task_id, template_name, file_name)

    async def delete_task(self, task_id):
        self.events.append("delete_task")
        self.deleted.append(task_id)


class FileServiceStub:
    def __init__(self, events, create_error=None):
        self.events = events
        self.create_error = create_error
        self.deleted = []

    async def create_new_task_result_dir(self, task_id, template_name):
        self.events.append("create_dir")
        if self.create_error:
            raise self.create_error

    def delete_task_result_dir(self, task_id):
        self.events.append("delete_dir")
        self.deleted.append(task_id)


class QueueStub:
    def __init__(self, events, error=None):
        self.events = events
        self.error = error
        self.jobs = []

    def put_nowait(self, job):
        self.events.append("enqueue")
        if self.error:
            raise self.error
        self.jobs.append(job)


def install_stubs(monkeypatch, *, create_error=None, queue_error=None):
    events = []
    task_mgr = TaskManagerStub(events)
    file_svc = FileServiceStub(events, create_error=create_error)
    queue = QueueStub(events, error=queue_error)
    monkeypatch.setattr(render, "task_mgr", task_mgr)
    monkeypatch.setattr(render, "file_svc", file_svc)
    monkeypatch.setattr(render, "render_queue", queue)
    return events, task_mgr, file_svc, queue


async def test_create_render_task_prepares_resources_before_enqueue(monkeypatch):
    events, task_mgr, _, queue = install_stubs(monkeypatch)
    req = DataRequest(data={})

    task_id = await render.create_render_task("invoice.docx", req)

    assert events == ["create_task", "create_dir", "enqueue"]
    assert task_mgr.created[2] == "invoice.docx"
    assert queue.jobs[0].task_id == uuid.UUID(task_id)


async def test_create_render_task_preserves_requested_file_name(monkeypatch):
    _, task_mgr, _, _ = install_stubs(monkeypatch)
    req = DataRequest(expectName="rendered-invoice", data={})

    await render.create_render_task("invoice.docx", req)

    assert task_mgr.created[2] == "rendered-invoice"


async def test_create_render_task_cleans_up_when_directory_creation_fails(monkeypatch):
    events, task_mgr, file_svc, _ = install_stubs(
        monkeypatch,
        create_error=OSError("cannot create directory"),
    )

    with pytest.raises(OSError, match="cannot create directory"):
        await render.create_render_task("invoice.docx", DataRequest(data={}))

    task_id = task_mgr.created[0]
    assert events == ["create_task", "create_dir", "delete_task", "delete_dir"]
    assert task_mgr.deleted == [task_id]
    assert file_svc.deleted == [task_id]


async def test_create_render_task_cleans_up_when_queue_is_full(monkeypatch):
    events, task_mgr, file_svc, _ = install_stubs(
        monkeypatch,
        queue_error=asyncio.QueueFull(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await render.create_render_task("invoice.docx", DataRequest(data={}))

    task_id = task_mgr.created[0]
    assert exc_info.value.status_code == 429
    assert events == [
        "create_task",
        "create_dir",
        "enqueue",
        "delete_task",
        "delete_dir",
    ]
    assert task_mgr.deleted == [task_id]
    assert file_svc.deleted == [task_id]
