"""
OCR Engine — extracts text and reports exactly what method was used.

Returns a dict:
  {
    "text":    str,   # extracted text (empty string if OCR failed/not available)
    "method":  str,   # "opencv+tesseract" | "pillow+tesseract" | "pymupdf_native" | "none"
    "success": bool,  # True only if real OCR actually ran and produced text
    "detail":  str,   # human-readable explanation shown in the UI
  }
"""

import os
import tempfile

# ── Check what's installed ───────────────────────────────────────────────────

try:
    import numpy as np
    import cv2
    CV2_OK = True
except Exception:
    CV2_OK = False

try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import pytesseract
    pytesseract.get_tesseract_version()
    TESS_OK = True
except Exception:
    TESS_OK = False

try:
    import fitz          # PyMuPDF
    FITZ_OK = True
except ImportError:
    FITZ_OK = False

print(
    f"[ocr_engine] opencv={CV2_OK}  pillow={PIL_OK}  "
    f"tesseract={TESS_OK}  pymupdf={FITZ_OK}"
)


# ── Public API ───────────────────────────────────────────────────────────────

def extract_text(path: str) -> dict:
    """
    Extract text from image or PDF.
    Always returns {"text", "method", "success", "detail"}.
    Never returns mock/dummy text — text is empty string if extraction fails.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _from_pdf(path)
    return _from_image(path)


# ── Image OCR ────────────────────────────────────────────────────────────────

def _from_image(path: str) -> dict:
    if TESS_OK and CV2_OK:
        try:
            text = _ocr_opencv(path)
            return {
                "text":    text,
                "method":  "opencv+tesseract",
                "success": bool(text.strip()),
                "detail":  "OCR performed — OpenCV preprocessing + Tesseract",
            }
        except Exception as e:
            print(f"[ocr] opencv+tesseract failed: {e}")

    if TESS_OK and PIL_OK:
        try:
            text = _ocr_pillow(path)
            return {
                "text":    text,
                "method":  "pillow+tesseract",
                "success": bool(text.strip()),
                "detail":  "OCR performed — Pillow preprocessing + Tesseract",
            }
        except Exception as e:
            print(f"[ocr] pillow+tesseract failed: {e}")

    missing = []
    if not TESS_OK:
        missing.append("Tesseract (https://github.com/UB-Mannheim/tesseract/wiki)")
    if not CV2_OK and not PIL_OK:
        missing.append("OpenCV or Pillow")

    return {
        "text":    "",
        "method":  "none",
        "success": False,
        "detail":  f"OCR NOT performed — missing: {', '.join(missing)}",
    }


# ── PDF extraction ────────────────────────────────────────────────────────────

def _from_pdf(path: str) -> dict:
    if not FITZ_OK:
        return {
            "text":    "",
            "method":  "none",
            "success": False,
            "detail":  "OCR NOT performed — PyMuPDF not installed. Run: pip install PyMuPDF",
        }

    doc = fitz.open(path)
    pages_text = []
    methods_used = set()

    for page in doc:
        native = page.get_text().strip()

        if native and len(native) > 20:
            pages_text.append(native)
            methods_used.add("pymupdf_native")
        elif TESS_OK:
            pix = page.get_pixmap(dpi=200)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(pix.tobytes("png"))
                tmp_path = tmp.name
            try:
                if CV2_OK:
                    text = _ocr_opencv(tmp_path)
                    methods_used.add("pymupdf+opencv+tesseract")
                elif PIL_OK:
                    text = _ocr_pillow(tmp_path)
                    methods_used.add("pymupdf+pillow+tesseract")
                else:
                    text = ""
                if text:
                    pages_text.append(text)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            methods_used.add("failed_no_tesseract")

    doc.close()
    combined = "\n".join(pages_text).strip()

    if not combined:
        return {
            "text":    "",
            "method":  "none",
            "success": False,
            "detail":  (
                "OCR NOT performed — PDF has no embedded text and Tesseract is not installed. "
                "Install Tesseract to OCR scanned PDFs."
            ),
        }

    method = ", ".join(sorted(methods_used))
    native_only = all("native" in m for m in methods_used)

    return {
        "text":    combined,
        "method":  method,
        "success": True,
        "detail":  (
            "Text extracted from PDF embedded content (no OCR needed — PDF has selectable text)"
            if native_only
            else f"OCR performed on scanned PDF — {method}"
        ),
    }


# ── OCR implementations ──────────────────────────────────────────────────────

def _ocr_opencv(path: str) -> str:
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    binary   = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp  = cv2.filter2D(binary, -1, kernel)
    return pytesseract.image_to_string(sharp, config="--oem 3 --psm 6").strip()


def _ocr_pillow(path: str) -> str:
    img = Image.open(path).convert("L")
    img = img.filter(ImageFilter.MedianFilter(3))
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    return pytesseract.image_to_string(img, config="--oem 3 --psm 6").strip()
