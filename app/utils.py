import re

TOKEN_RE = re.compile(r"\w+|[^\w\s]+", re.UNICODE)

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(TOKEN_RE.findall(text)) // 1)
