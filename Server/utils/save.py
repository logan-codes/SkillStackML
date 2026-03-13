import os
import tempfile

def _save(content: bytes, filename: str) -> str:
    ext = os.path.splitext(filename or "cert.png")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"}:
        ext = ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
        f.write(content); return f.name
