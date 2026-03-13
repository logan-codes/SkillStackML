import os
import tempfile
import numpy as np
import cv2
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
import fitz

from core.logger import logger

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


# Image OCR 
def _from_image(path: str) -> dict:
    try:
        text = _ocr_opencv(path)
        logger.info("[ocr-image] opencv+tesseract successfull.")
        return {
            "text":    text,
            "method":  "opencv+tesseract",
            "success": bool(text.strip()),
            "detail":  "OCR performed — OpenCV preprocessing + Tesseract",
        }
    except Exception as e:
        logger.warning(f"[ocr-image] opencv+tesseract failed: {e}")
        try:
            text = _ocr_pillow(path)
            logger.info("[ocr-image] pillow+tessearct successfull.")
            return {
                "text":    text,
                "method":  "pillow+tesseract",
                "success": bool(text.strip()),
                "detail":  "OCR performed — Pillow preprocessing + Tesseract",
            }
        except Exception as e:
            logger.warning(f"[ocr-image] pillow+tesseract failed: {e}")

def _from_pdf(path: str) -> dict:
    doc = fitz.open(path)
    pages_text = []
    methods_used = ""

    for page in doc:
        native = page.get_text().strip()
        if native and len(native) > 20:
            pages_text.append(native)
            methods_used="pymupdf_native"
        else:
            pix = page.get_pixmap(dpi=200)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(pix.tobytes("png"))
                tmp_path = tmp.name
            try:
                text = _from_image(tmp_path)
            except Exception as e:
                logger.warning("[ocr-pdf] Failed")
            finally:
                if text:
                    pages_text.append(text)
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
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


# OCR implementations 
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
