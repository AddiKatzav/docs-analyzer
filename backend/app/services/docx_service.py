from pathlib import Path
from uuid import uuid4

from docx import Document
from fastapi import UploadFile

from app.services.paths import UPLOADS_DIR, ensure_data_dirs


def save_uploaded_docx(upload_file: UploadFile) -> tuple[Path, str]:
    ensure_data_dirs()
    ext = Path(upload_file.filename or "document.docx").suffix.lower()
    if ext != ".docx":
        raise ValueError("Only .docx files are supported.")
    file_name = upload_file.filename or "document.docx"
    storage_name = f"{uuid4().hex}{ext}"
    storage_path = UPLOADS_DIR / storage_name
    storage_path.write_bytes(upload_file.file.read())
    return storage_path, file_name


def extract_docx_text(docx_path: Path) -> str:
    document = Document(str(docx_path))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
