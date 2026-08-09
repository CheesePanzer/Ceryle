class ServiceException(Exception):
    def __init__(self, status_code: int, message: str, error_code: int | None):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code

class SFileNotFoundError(ServiceException):
    def __init__(self, file_name: str):
        super().__init__(404,f"File {file_name} Not Found",404)

class SFileExistsError(ServiceException):
    def __init__(self, file_name: str):
        super().__init__(500, f"File {file_name} Already Exists", 500)

class SFileTypeError(ServiceException):
    def __init__(self, file_name: str):
        super().__init__(500, f"File {file_name} Is Not A Docx", 500)

class SFileInvalidOperationError(ServiceException):
    def __init__(self, file_name: str, invalid_operations: str):
        super().__init__(500, f"File {file_name} Doesn't allow {invalid_operations}", 500)

class SInvalidImageSourceError(ServiceException):
    def __init__(self, source: str, reason: str = "Not a valid base64 data URI or URL"):
        super().__init__(
            status_code=400,
            message=f"Invalid image source: {reason}",
            error_code=404
        )

class SImageFetchError(ServiceException):
    def __init__(self, url: str, reason: str):
        super().__init__(
            status_code=502,
            message=f"Failed to fetch image from {url}: {reason}",
            error_code=502
        )