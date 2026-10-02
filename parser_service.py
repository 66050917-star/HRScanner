"""อ่านไฟล์ (PDF / DOCX / TXT / รูป) -> ข้อความ
PDF สแกน: แปลงเป็นรูปทีละหน้าในเครื่อง (PyMuPDF) แล้วส่งให้โมเดล Vision ถอดข้อความ — ใช้ได้กับทุกโมเดลที่รับรูปภาพ"""
import io
from llm_service import get_key, vision_text, provider

IMG = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
MAX_PAGES = 6

def _need(pkg): raise ValueError(f"ยังไม่ได้ติดตั้ง {pkg} — รัน: pip install -r requirements.txt")

def _ocr(images):
    if not get_key():
        raise ValueError(f"ไฟล์นี้เป็นภาพสแกน/รูปภาพ ต้องใช้ API key ของ {provider()} เพื่ออ่านข้อความ (ใส่ที่แถบด้านข้าง) หรือวางข้อความแทน")
    try: return "\n\n".join(vision_text(b, m) for b, m in images).strip()
    except RuntimeError as e: raise ValueError(f"อ่านภาพไม่สำเร็จ: {e}")

def _pdf_pages(data):
    try: import fitz
    except ImportError: _need("pymupdf")
    doc = fitz.open(stream=data, filetype="pdf")
    return [(doc[i].get_pixmap(dpi=170).tobytes("png"), "image/png") for i in range(min(len(doc), MAX_PAGES))]

def read_upload(f) -> str:
    name = (f.filename or "").lower(); ext = name.rsplit(".", 1)[-1]; data = f.read()
    if ext == "pdf":
        try: from pypdf import PdfReader
        except ImportError: _need("pypdf")
        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages).strip()
        return text if len(text) > 30 else _ocr(_pdf_pages(data))   # ไม่มีตัวหนังสือ = สแกน
    if ext == "docx":
        try: from docx import Document
        except ImportError: _need("python-docx")
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs).strip()
    if ext == "txt": return data.decode("utf-8", errors="ignore")
    if ext in IMG: return _ocr([(data, IMG[ext])])
    raise ValueError("รองรับ PDF, DOCX, TXT, PNG, JPG เท่านั้น")
