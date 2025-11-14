import fitz  # pymupdf
from pdfminer.high_level import extract_text as pdfminer_extract
from docx import Document
import os

def extract_text_from_pdf(path: str) -> str:
    try:
        doc = fitz.open(path)
        pages = []
        for i in range(len(doc)):
            page = doc.load_page(i)
            text = page.get_text("text")
            pages.append(text)
        return "\n\n[PAGE_BREAK]\n\n".join(pages)
    except Exception:
        return pdfminer_extract(path)

def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    paras = [p.text for p in doc.paragraphs]
    return "\n\n".join(paras)

def extract_text(path: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".pdf"]:
        return extract_text_from_pdf(path)
    if ext in [".docx"]:
        return extract_text_from_docx(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
