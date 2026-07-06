from io import BytesIO
from typing import List

import jinja2
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2 import pass_context, Undefined

from docservice.baseclasses import ImageData
from docservice.imageresolver import ImageResolver
from docservice.safeenv import SafeEnvironment, SilentUndefined


class RenderService:
    """
    Responsible for rendering a docx template with given data and images.
    Does not know about file paths, caching, or storage - it only renders.
    """

    def __init__(self, image_fetch_timeout: float = 10.0):
        self.image_fetch_timeout = image_fetch_timeout
        self._jinja_env = self._build_jinja_env()

    @staticmethod
    def _build_jinja_env() -> jinja2.Environment:
        env = SafeEnvironment(undefined=SilentUndefined)

        @pass_context
        def inline_image_filter(ctx, value, width=None, height=None):
            """
                {{ image_variable | img(width=50, height=40) }}
            """
            if isinstance(value, Undefined):
                return "{{ WARNING: Picture Not Found }}"

            tpl = ctx["__tpl__"]
            w = Mm(float(width)) if width else None
            h = Mm(float(height)) if height else None
            return InlineImage(tpl, value, width=w, height=h)

        env.filters["img"] = inline_image_filter
        return env

    def render(self, template_bytes: bytes, data: dict, images: List[ImageData] | None) -> BytesIO:
        """
        Render a docx template from raw bytes with given data and images.
        Returns a BytesIO stream of the resulting .docx file.
        """
        doc = DocxTemplate(BytesIO(template_bytes))

        for image in (images or []):
            img_stream = ImageResolver.resolve_image_source(image.imageSource, timeout=self.image_fetch_timeout)
            data[image.varName] = img_stream
            if image.realName:
                data[f"{image.varName}_realname"] = image.realName

        data["__tpl__"] = doc

        doc.render(data, self._jinja_env)

        stream = BytesIO()
        doc.save(stream)
        stream.seek(0)
        return stream