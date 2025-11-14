import re
from typing import List
from .utils import estimate_tokens

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

def chunk_text(text: str, chunk_tokens: int = 400, overlap: int = 100) -> List[dict]:
    sentences = SENTENCE_SPLIT.split(text)
    chunks = []
    cur = []
    cur_tokens = 0
    chunk_id = 0
    for s in sentences:
        t = estimate_tokens(s)
        if cur_tokens + t > chunk_tokens and cur:
            content = " ".join(cur)
            chunks.append({"chunk_id": f"c_{chunk_id}", "content": content})
            chunk_id += 1
            # keep overlap worth of sentences
            keep = []
            keep_tokens = 0
            while cur and keep_tokens < overlap:
                sent = cur.pop()
                keep.insert(0, sent)
                keep_tokens += estimate_tokens(sent)
            cur = keep
            cur_tokens = sum(estimate_tokens(x) for x in cur)
        cur.append(s)
        cur_tokens += t
    if cur:
        chunks.append({"chunk_id": f"c_{chunk_id}", "content": " ".join(cur)})
    return chunks
