"""
QR Scanner — finds and decodes QR codes from certificate images/PDFs.

Strategy:
  1. Try pyzbar (fastest, most reliable)
  2. Try OpenCV QRCodeDetector (no extra deps)
  3. Try zxing-cpp if available

Returns:
  {
    "found":   bool,
    "url":     str,   # decoded URL from QR (empty if not found)
    "data":    str,   # raw QR data
    "method":  str,
    "detail":  str,
  }
"""

import os
import tempfile

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_OK = True
except ImportError:
    PYZBAR_OK = False

try:
    import cv2
    import numpy as np
    CV2_OK = True
except Exception:
    CV2_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import fitz
    FITZ_OK = True
except ImportError:
    FITZ_OK = False

print(f"[qr_scanner] pyzbar={PYZBAR_OK}  cv2={CV2_OK}  pillow={PIL_OK}  pymupdf={FITZ_OK}")


def scan_qr(path: str) -> dict:
    """
    Scan a certificate image or PDF for QR codes.
    Returns the first valid URL found.
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        return _scan_pdf(path)
    else:
        return _scan_image(path)


def _scan_image(path: str) -> dict:
    """Try multiple methods to decode QR from image."""

    # Method 0: NPTEL-specific — crop exact QR region before scanning
    # NPTEL certificates always have the QR at pixel region (3544, 4664, 3973, 5058)
    # Cropping first makes pyzbar far more reliable on high-res NPTEL PDFs
    if PYZBAR_OK and PIL_OK:
        try:
            img = Image.open(path)
            nptel_qr_box = (3544, 4664, 3973, 5058)
            if img.width >= 3973 and img.height >= 5058:
                cropped_qr = img.crop(nptel_qr_box)
                result = _try_pyzbar(cropped_qr)
                if result["found"]:
                    result["method"] = "pyzbar+nptel_crop"
                    print(f"[qr] NPTEL crop scan succeeded: {result['data'][:60]}")
                    return result
        except Exception as e:
            print(f"[qr] nptel crop scan failed: {e}")

    # Method 1: pyzbar on full image
    if PYZBAR_OK and PIL_OK:
        try:
            img = Image.open(path)
            result = _try_pyzbar(img)
            if result["found"]:
                result["method"] = "pyzbar"
                return result
        except Exception as e:
            print(f"[qr] pyzbar failed: {e}")

    # Method 2: OpenCV QRCodeDetector
    if CV2_OK:
        try:
            result = _try_opencv(path)
            if result["found"]:
                result["method"] = "opencv"
                return result
        except Exception as e:
            print(f"[qr] opencv failed: {e}")

    # Method 3: Try with image preprocessing (for low quality scans)
    if CV2_OK and (PYZBAR_OK and PIL_OK):
        try:
            result = _try_preprocessed(path)
            if result["found"]:
                result["method"] = "preprocessed+pyzbar"
                return result
        except Exception as e:
            print(f"[qr] preprocessed scan failed: {e}")

    return {
        "found":  False,
        "url":    "",
        "data":   "",
        "method": "none",
        "detail": (
            "No QR code found in the certificate. "
            + ("" if PYZBAR_OK else "Install pyzbar for better detection: pip install pyzbar ")
            + "Make sure the certificate image is clear and not heavily compressed."
        ),
    }


def _scan_pdf(path: str) -> dict:
    """Extract pages from PDF and scan each for QR."""
    if not FITZ_OK:
        return {
            "found": False, "url": "", "data": "", "method": "none",
            "detail": "PyMuPDF not installed — cannot scan PDF for QR codes.",
        }

    doc = fitz.open(path)
    for page_num, page in enumerate(doc):
        # Render at high DPI for good QR detection
        pix = page.get_pixmap(dpi=200)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(pix.tobytes("png"))
            tmp_path = tmp.name
        try:
            result = _scan_image(tmp_path)
            if result["found"]:
                result["detail"] = f"QR found on PDF page {page_num + 1}"
                doc.close()
                return result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    doc.close()
    return {
        "found": False, "url": "", "data": "", "method": "none",
        "detail": "No QR code found in any PDF page.",
    }


def _try_pyzbar(pil_img) -> dict:
    from pyzbar.pyzbar import decode
    import PIL.Image

    # Try original
    results = decode(pil_img)
    for r in results:
        data = r.data.decode("utf-8", errors="ignore").strip()
        if data:
            url = data if data.startswith("http") else ""
            return {"found": True, "url": url, "data": data,
                    "detail": f"QR decoded: {data[:100]}"}

    # Try grayscale
    gray = pil_img.convert("L")
    results = decode(gray)
    for r in results:
        data = r.data.decode("utf-8", errors="ignore").strip()
        if data:
            url = data if data.startswith("http") else ""
            return {"found": True, "url": url, "data": data,
                    "detail": f"QR decoded: {data[:100]}"}

    return {"found": False, "url": "", "data": "", "detail": ""}


def _try_opencv(path: str) -> dict:
    img = cv2.imread(path)
    if img is None:
        return {"found": False, "url": "", "data": "", "detail": ""}

    detector = cv2.QRCodeDetector()

    # Try on original
    data, _, _ = detector.detectAndDecode(img)
    if data:
        url = data if data.startswith("http") else ""
        return {"found": True, "url": url, "data": data,
                "detail": f"QR decoded: {data[:100]}"}

    # Try on grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    data, _, _ = detector.detectAndDecode(gray)
    if data:
        url = data if data.startswith("http") else ""
        return {"found": True, "url": url, "data": data,
                "detail": f"QR decoded: {data[:100]}"}

    return {"found": False, "url": "", "data": "", "detail": ""}


def _try_preprocessed(path: str) -> dict:
    """Aggressively preprocess image to help with low-quality scans."""
    from pyzbar.pyzbar import decode
    from PIL import Image

    img_cv = cv2.imread(path)
    if img_cv is None:
        return {"found": False, "url": "", "data": "", "detail": ""}

    attempts = []

    # 1. Upscale 2x
    upscaled = cv2.resize(img_cv, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    attempts.append(upscaled)

    # 2. Sharpen
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(img_cv, -1, kernel)
    attempts.append(sharp)

    # 3. Binary threshold
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    attempts.append(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))

    # 4. Adaptive threshold
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 11, 2)
    attempts.append(cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR))

    for attempt_img in attempts:
        pil = Image.fromarray(cv2.cvtColor(attempt_img, cv2.COLOR_BGR2RGB))
        results = decode(pil)
        for r in results:
            data = r.data.decode("utf-8", errors="ignore").strip()
            if data:
                url = data if data.startswith("http") else ""
                return {"found": True, "url": url, "data": data,
                        "detail": f"QR decoded after preprocessing: {data[:100]}"}

    return {"found": False, "url": "", "data": "", "detail": ""}
