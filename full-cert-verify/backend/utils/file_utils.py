"""
utils/file_utils.py
───────────────────
Shared file utilities used across all workflows.

Provides:
    save_temp_file(contents, filename) -> str   — save bytes to a temp file
    to_image_bytes(contents, content_type)      — convert PDF/image to JPEG bytes
    normalize_date(text)                        — date string normalizer
    normalize(text)                             — generic text normalizer
"""

import io
import os
import re
import tempfile
from PIL import Image


# ── Month lookup ─────────────────────────────────────────────
MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
    "january":1,"february":2,"march":3,"april":4,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}


def normalize(text: str) -> str:
    """Strip extra whitespace and lowercase for comparison."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip().lower()


def normalize_date(text: str) -> str:
    """
    Normalize a date string to YYYY-MM-DD for reliable comparison.
    Handles formats like 'May 13, 2022', 'Aug 22, 2024', 'Jul-Oct 2024', etc.
    Returns the original string lowercased if no pattern matches.
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip().lower())
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
    m = re.search(
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})',
        text,
    )
    if m:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
    return text


def save_temp_file(contents: bytes, filename: str) -> str:
    """
    Write raw bytes to a named temp file and return the file path.
    Caller is responsible for deleting the file after use.
    """
    ext = os.path.splitext(filename or "cert.png")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"}:
        ext = ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
        f.write(contents)
        return f.name


def to_image_bytes(contents: bytes, content_type: str, dpi: int = 200) -> bytes:
    """
    Convert an uploaded PDF or image file to JPEG bytes suitable for
    sending to a Vision AI model.

    Args:
        contents:     Raw file bytes.
        content_type: MIME type e.g. "application/pdf" or "image/jpeg".
        dpi:          Render DPI for PDF pages (default 200).

    Returns:
        JPEG bytes of the first page / full image.
    """
    if content_type == "application/pdf":
        import fitz  # PyMuPDF
        pdf = fitz.open(stream=contents, filetype="pdf")
        page = pdf.load_page(0)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    else:
        img = Image.open(io.BytesIO(contents))
        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.LANCZOS)

    # JPEG does not support transparency — convert RGBA/P/LA to RGB
    if img.mode in ("RGBA", "P", "LA", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()
