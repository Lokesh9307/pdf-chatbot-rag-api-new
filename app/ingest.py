import os
import time
import uuid
from .extractors import extract_text
from .chunker import chunk_text
from .db import insert_doc, insert_chunks

def ingest_file(path: str, filename: str, user_id: str = "user") -> str:
    doc_id = str(uuid.uuid4())
    created_at = int(time.time())
    text = extract_text(path, filename)
    pages = text.split("\n\n[PAGE_BREAK]\n\n") if "[PAGE_BREAK]" in text else [text]
    chunk_records = []
    for p_idx, page_text in enumerate(pages):
        chunks = chunk_text(page_text)
        for c in chunks:
            chunk_id = f"{doc_id}_{c['chunk_id']}"
            chunk_records.append((chunk_id, doc_id, p_idx + 1, c['content']))
    insert_doc(doc_id, user_id, filename, created_at)
    insert_chunks(chunk_records)
    try:
        os.remove(path)
    except Exception:
        pass
    return doc_id
