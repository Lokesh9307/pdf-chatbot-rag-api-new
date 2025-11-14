import sqlite3
import os
from typing import List, Tuple, Optional

# Path to DB - change via env var if needed
DB_PATH = os.environ.get("RAG_DB_PATH", "/app/data/rag.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS docs (
  doc_id TEXT PRIMARY KEY,
  user_id TEXT,
  filename TEXT,
  created_at INTEGER
);

-- chunks is an FTS5 virtual table; columns: chunk_id (identifier), doc_id (normal column), page, content
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
  chunk_id UNINDEXED,
  doc_id UNINDEXED,
  page UNINDEXED,
  content,
  tokenize='porter'
);
"""

def get_conn():
    # ensure folder exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # WAL for concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

_conn = get_conn()
# create schema if missing
_conn.executescript(SCHEMA)
_conn.commit()

def insert_doc(doc_id: str, user_id: str, filename: str, created_at: int):
    """Insert or update a document record."""
    _conn.execute(
        "INSERT OR REPLACE INTO docs(doc_id, user_id, filename, created_at) VALUES (?, ?, ?, ?)",
        (doc_id, user_id, filename, created_at),
    )
    _conn.commit()

def insert_chunks(chunks: List[Tuple[str, str, int, str]]):
    """
    Insert many chunk records.
    chunks: list of tuples -> (chunk_id, doc_id, page, content)
    """
    if not chunks:
        return
    _conn.executemany(
        "INSERT INTO chunks(chunk_id, doc_id, page, content) VALUES (?, ?, ?, ?)",
        chunks,
    )
    _conn.commit()

def search(query: str, k: int = 10, doc_id: Optional[str] = None):
    """
    Search chunks for `query`. If doc_id is provided, restrict to that document.
    Returns list of dicts: {chunk_id, doc_id, page, content, score}
    """
    cur = _conn.cursor()
    try:
        if doc_id:
            # Use FTS5 match plus doc_id filter
            cur.execute(
                "SELECT chunk_id, doc_id, page, content, bm25(chunks) as score FROM chunks WHERE doc_id = ? AND chunks MATCH ? LIMIT ?",
                (doc_id, query, k),
            )
        else:
            cur.execute(
                "SELECT chunk_id, doc_id, page, content, bm25(chunks) as score FROM chunks WHERE chunks MATCH ? LIMIT ?",
                (query, k),
            )
    except sqlite3.OperationalError:
        # bm25 might not be available in all sqlite builds; fallback to simpler select
        if doc_id:
            cur.execute(
                "SELECT chunk_id, doc_id, page, content FROM chunks WHERE doc_id = ? AND chunks MATCH ? LIMIT ?",
                (doc_id, query, k),
            )
        else:
            cur.execute(
                "SELECT chunk_id, doc_id, page, content FROM chunks WHERE chunks MATCH ? LIMIT ?",
                (query, k),
            )

    rows = cur.fetchall()
    results = []
    for r in rows:
        # row shapes: (chunk_id, doc_id, page, content) or (chunk_id, doc_id, page, content, score)
        if len(r) == 4:
            chunk_id, doc_id_r, page, content = r
            score = 0.0
        else:
            chunk_id, doc_id_r, page, content, score = r
        results.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id_r,
                "page": page,
                "content": content,
                "score": float(score) if score is not None else 0.0,
            }
        )
    return results

def get_top_chunks(k: int = 5, doc_id: Optional[str] = None):
    """
    Fast fallback: return top-k chunks by insertion order (rowid). If doc_id provided,
    limit to that document. Useful for generic 'summarize' intents when no matches exist.
    """
    cur = _conn.cursor()
    try:
        if doc_id:
            cur.execute(
                "SELECT chunk_id, doc_id, page, content FROM chunks WHERE doc_id = ? LIMIT ?",
                (doc_id, k),
            )
        else:
            cur.execute("SELECT chunk_id, doc_id, page, content FROM chunks LIMIT ?", (k,))
    except sqlite3.OperationalError:
        # Fallback if any strange error; try the same queries (should normally work)
        if doc_id:
            cur.execute(
                "SELECT chunk_id, doc_id, page, content FROM chunks WHERE doc_id = ? LIMIT ?",
                (doc_id, k),
            )
        else:
            cur.execute("SELECT chunk_id, doc_id, page, content FROM chunks LIMIT ?", (k,))
    rows = cur.fetchall()
    results = []
    for r in rows:
        chunk_id, doc_id_r, page, content = r
        results.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id_r,
                "page": page,
                "content": content,
                "score": 0.0,
            }
        )
    return results
