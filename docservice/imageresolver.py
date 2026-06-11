import base64
import binascii
import io
from io import BytesIO

import httpx

from docservice.exceptions import SInvalidImageSourceError, SImageFetchError


class ImageResolver:
    @staticmethod
    def resolve_image_source(source: str, timeout: float = 10.0) -> BytesIO:

        """
        Resolve an image source string into a BytesIO stream.

        Accepted formats:
        - Base64 data URI: must start with 'data:' and contain a comma
          e.g. "data:image/png;base64,iVBORw0KG..."
        - URL: must start with 'http://' or 'https://'

        Anything else raises SInvalidImageSourceError.
        """
        if source.startswith("data:") and "," in source:
            return ImageResolver._decode_base64(source)

        if source.startswith("http://") or source.startswith("https://"):
            return ImageResolver._fetch_url(source, timeout=timeout)

        raise SInvalidImageSourceError(source)

    @staticmethod
    def _decode_base64(source: str) -> BytesIO:
        _, b64_data = source.split(",", 1)
        try:
            img_bytes = base64.b64decode(b64_data, validate=True)
        except (binascii.Error, ValueError) as e:
            raise SInvalidImageSourceError(source, reason=f"Invalid base64 data: {e}")

        return io.BytesIO(img_bytes)

    @staticmethod
    def _fetch_url(url: str, timeout: float) -> BytesIO:
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SImageFetchError(url, reason=str(e))

        return io.BytesIO(resp.content)
