# backend/app/models.py
from pydantic import BaseModel
from typing import List, Optional

class UploadResponse(BaseModel):
    doc_id: str

class QueryRequest(BaseModel):
    query: str
    k: Optional[int] = 5
    use_groq: Optional[bool] = False
    doc_id: Optional[str] = None   # NEW: optional doc_id to scope search

class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    page: int
    content: str
    score: float

class QueryResponse(BaseModel):
    results: List[Chunk]
    answer: Optional[str] = None
