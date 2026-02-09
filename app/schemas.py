from pydantic import BaseModel
from fastapi_users import schemas
import uuid

class PostCreate(BaseModel):
    title: str
    content: str

class PostResponse(BaseModel):
    title: str
    content: str

class UserRead(schemas.BaseUser[uuid.UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

class OCRDocument(BaseModel):
    filename: str
    handwritten: bool
    language: str
    text: str
    notes: str

class OCRResult(BaseModel):
    status: str
    document: OCRDocument

class OCRResponse(BaseModel):
    status: str
    filename: str
    model: str
    elapsed_ms: int
    usage: dict
    ocr: OCRResult
