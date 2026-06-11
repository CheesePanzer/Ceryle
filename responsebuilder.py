from io import BytesIO
from typing import BinaryIO
from starlette.responses import StreamingResponse, FileResponse


class ResponseBuilder:
    @staticmethod
    def build_file_response(content: BytesIO | BinaryIO,expect_name:str, file_hash: str, is_hit: bool) -> StreamingResponse:
        if expect_name.endswith(".docx"):
            expect_name = expect_name.replace(".docx", "")

        return StreamingResponse(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename={expect_name}.docx".encode('utf-8').decode('latin-1'),
            "X-File-Hash": file_hash,
            "X-Is-Cache": "Y" if is_hit else "N",
        }
    )

    @staticmethod
    def build_file_response_usePath(file_path: str, expect_name: str, file_hash: str, is_hit: bool) -> FileResponse:
        if expect_name.endswith(".docx"):
            expect_name = expect_name.replace(".docx", "")

        return FileResponse(
            path=file_path,
            filename=f"{expect_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "X-File-Hash": file_hash,
                "X-Is-Cache": "Y" if is_hit else "N",
            }
        )