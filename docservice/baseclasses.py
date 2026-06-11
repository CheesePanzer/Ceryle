from typing import Dict, List,  Any
from pydantic import BaseModel, Field

class ImageData(BaseModel):
    varName: str = Field(..., description="Variable name in the docx template")
    imageSource: str = Field(..., description="Base64 or Url")
    realName: str | None = Field(None, description="The title or the image")

class DataRequest(BaseModel):
    expectName: str | None = Field(None, description="The expect name of the returned file with or without extension")
    data: Dict[str, Any] = Field(..., description="The Json Format Data")
    images: List[ImageData] | None = Field(None, description="Optional image data list")