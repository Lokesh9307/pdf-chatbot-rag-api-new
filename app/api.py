from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
import time
import requests
import json
import re
from typing import List, Optional
from dotenv import load_dotenv

# local imports
from .ingest import ingest_file
from .models import QueryRequest
from .db import search, get_top_chunks

load_dotenv()

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Groq configuration (set these in environment)
GROQ_API_URL = os.environ.get("GROQ_API_URL")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user_id: str = Form("user")):
    """
    Save uploaded file and run ingestion (extract -> chunk -> insert).
    Returns a doc_id (UUID).
    """
    ts = int(time.time())
    filename = file.filename
    dest_path = os.path.join(UPLOAD_DIR, f"{ts}_{filename}")
    with open(dest_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    doc_id = ingest_file(dest_path, filename, user_id)
    return JSONResponse({"doc_id": doc_id})


def is_generic_summary_intent(query: str) -> bool:
    """
    Conservative detection for generic summary-style questions.
    """
    if not query:
        return False
    q = query.strip().lower()
    summary_patterns = [
        r"\bsummariz(e|ation|e it)?\b",
        r"\bsummary\b",
        r"\bgive (me )?a (summary|brief|gist|tl;dr)\b",
        r"\btl;dr\b",
        r"\bgive (me )?an overview\b",
        r"\bwhat's the (main|key) (point|points)\b",
        r"\bkey takeaways\b",
        r"\bwhat is this document about\b",
        r"\bgist\b",
    ]
    for pat in summary_patterns:
        if re.search(pat, q):
            return True
    return False


def build_prompt(query: str, chunks: List[dict]) -> str:
    """
    Build a concise prompt containing top chunks and the user question.
    """
    header = (
        "You are a helpful assistant. Use only the provided document excerpts to answer the question. "
        "Cite the source chunk ids and pages in bracketed form. If the answer cannot be found, say you don't know. Be concise.\n\n"
    )
    doc_snippets = []
    for i, c in enumerate(chunks):
        # Keep snippet content as-is; LLM will be constrained by system message
        snippet = f"[{i+1}] (chunk_id={c['chunk_id']}, doc={c['doc_id']}, page={c['page']})\n{c['content']}\n"
        doc_snippets.append(snippet)
    prompt = header + "\n\n".join(doc_snippets) + f"\n\nQuestion: {query}\nAnswer:"
    # Truncate to a conservative limit to avoid sending huge payloads
    if len(prompt) > 15000:
        prompt = prompt[:15000]
    return prompt


def call_groq(prompt: str, timeout: int = 30) -> str:
    """
    Send an OpenAI-compatible chat request to Groq Cloud.
    Adjust payload if Groq requires a different schema for your account.
    """
    if not GROQ_API_URL or not GROQ_API_KEY:
        return "[Groq not configured]"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions using only the provided document excerpts. "
                "If the information is not present, say you don't know. Provide concise answers and cite the source chunk ids/pages."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        # optionally tune:
        # "temperature": 0.0,
        # "max_tokens": 512,
    }

    try:
        resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        return f"[Groq call failed (network/error): {e}]"

    if not resp.ok:
        body_text = resp.text
        try:
            body_json = resp.json()
            body_text = json.dumps(body_json, indent=2)
        except Exception:
            pass
        return f"[Groq request failed: status={resp.status_code} body={body_text}]"

    try:
        data = resp.json()
    except Exception as e:
        return f"[Groq response parse failed: {e} - raw={resp.text}]"

    # Try common response shapes
    if isinstance(data, dict):
        # choices -> message -> content
        choices = data.get("choices")
        if choices and isinstance(choices, list) and len(choices) > 0:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict) and "content" in msg:
                    return msg["content"]
                if "text" in first and isinstance(first["text"], str):
                    return first["text"]
                for key in ("text", "output", "generated_text", "content"):
                    if key in first and isinstance(first[key], str):
                        return first[key]
            if isinstance(first, str):
                return first

        # outputs array
        outputs = data.get("outputs")
        if outputs and isinstance(outputs, list) and len(outputs) > 0:
            out0 = outputs[0]
            if isinstance(out0, dict):
                for key in ("content", "text", "output", "generated_text"):
                    if key in out0 and isinstance(out0[key], str):
                        return out0[key]
            if isinstance(out0, str):
                return out0

        # top-level fallback keys
        for key in ("text", "output", "result", "generated_text"):
            if key in data and isinstance(data[key], str):
                return data[key]

    # fallback to raw text
    return resp.text


@router.post("/query")
async def query(q: QueryRequest):
    """
    Query endpoint.
    QueryRequest fields: query (str), k (opt int), use_groq (opt bool), doc_id (opt str)
    """
    # Use doc_id if provided to scope search
    doc_id = getattr(q, "doc_id", None)
    results = search(q.query, k=q.k or 5, doc_id=doc_id)
    response = {"results": results}

    # If Groq synthesis requested:
    if q.use_groq:
        # If no retrieved chunks -> fallback behavior
        if not results or len(results) == 0:
            if is_generic_summary_intent(q.query):
                # fallback to top chunks for doc or global
                fallback_chunks = get_top_chunks(k=q.k or 5, doc_id=doc_id)
                if fallback_chunks:
                    prompt = build_prompt(q.query, fallback_chunks)
                    llm_resp = call_groq(prompt)
                    response["results"] = fallback_chunks
                    response["answer"] = llm_resp
                    return JSONResponse(response)
                else:
                    response["answer"] = "No content indexed yet to summarize."
                    return JSONResponse(response)
            else:
                response["answer"] = "No relevant content found in the uploaded document(s) for your query."
                return JSONResponse(response)

        # Normal path: have results -> call Groq
        if not GROQ_API_URL or not GROQ_API_KEY:
            raise HTTPException(status_code=500, detail="Groq not configured on server")

        prompt = build_prompt(q.query, results)
        llm_resp = call_groq(prompt)
        response["answer"] = llm_resp
        return JSONResponse(response)

    # If not using Groq: provide extractive fallback for generic summary requests
    if not q.use_groq:
        if not results or len(results) == 0:
            if is_generic_summary_intent(q.query):
                fallback_chunks = get_top_chunks(k=q.k or 5, doc_id=doc_id)
                if fallback_chunks:
                    snippet_text = "\n\n".join([c["content"].strip() for c in fallback_chunks])
                    snippet_text = snippet_text[:4000]
                    response["answer"] = snippet_text
                    response["results"] = fallback_chunks
                    return JSONResponse(response)
                else:
                    response["answer"] = "No content indexed yet to summarize."
                    return JSONResponse(response)
            else:
                response["answer"] = "No relevant content found in the uploaded document(s) for your query."
                return JSONResponse(response)

    # Default: return retrieval results (possibly empty)
    return JSONResponse(response)
