# utils/clean_response.py
import re
from typing import Optional

def strip_provenance(text: Optional[str]) -> Optional[str]:
    if not text:
        return text

    out = text

    # 1) remove [1], [2] markers
    out = re.sub(r"\s*\[\s*\d+\s*\]\s*", " ", out)

    # 2) remove (chunk_id=..., doc=..., page=...) and similar
    out = re.sub(r"\s*\(\s*(?:chunk_id|chunkid|doc|doc_id)[^)]*\)\s*", " ", out, flags=re.IGNORECASE)

    # 3) remove explicit chunkid(...) variants
    out = re.sub(r"\s*\(\s*chunkid=[^)]*\)\s*", " ", out, flags=re.IGNORECASE)

    # 4) remove lines starting with 'Source:' or 'Sources:'
    out = re.sub(r"(?im)^\s*source[s]?:.*$", "", out)

    # 5) inline 'Source 1:' etc.
    out = re.sub(r"\bsource\s*\d*\b[:\s]*", "", out, flags=re.IGNORECASE)

    # 6) collapse repeated spaces/newlines and trim
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.strip()

    return out
