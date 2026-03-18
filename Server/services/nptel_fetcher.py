from core.logger import get_logger

import re, os, tempfile
import requests
from bs4 import BeautifulSoup
from .ocr_engine import extract_text

logger= get_logger(__name__)


NPTEL_BASE_URL = "https://internalapp.nptel.ac.in"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_nptel(url: str) -> dict:
    steps = []

    result = {
        "success": False, "text": "", "fields": {}, "url": url,
        "pdf_url": "", "ocr_method": "none", "detail": "", "steps": steps,
    }

    # ── Step 1: Fetch original QR URL, follow redirects (exactly like verifier.py) ──
    logger.info(f"Step 1: Fetching NPTEL page: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        logger.info(f"Step 1: HTTP {response.status_code}  final URL: {response.url}")
        if not response.ok:
            result["detail"] = f"Failed to load NPTEL page (HTTP {response.status_code})."
            return result
    except Exception as e:
        logger.info(f"Step 1 ERROR: {e}")
        result["detail"] = f"Could not connect to NPTEL: {e}"
        return result

    # ── Step 2: Parse with html5lib — exact same as verifier.py ──────────────
    logger.info("Step 2: Parsing page — looking for 'Course Certificate' button...")
    try:
        soup = BeautifulSoup(response.content, "html5lib")
    except Exception:
        soup = BeautifulSoup(response.content, "lxml")

    certificate_link = soup.find("a", string="Course Certificate")

    if not certificate_link:
        for a in soup.find_all("a"):
            if a.get_text(strip=True).lower() == "course certificate":
                certificate_link = a
                break

    if not certificate_link or not certificate_link.get("href"):
        all_links = [(a.get_text(strip=True), a.get("href", "")) for a in soup.find_all("a") if a.get_text(strip=True)]
        logger.info(f"Step 2: Button not found. Page links: {all_links[:10]}")
        logger.info(f"Step 2: Page text snippet: {response.text[:500]}")
        result["detail"] = (
            f"Could not find 'Course Certificate' button. "
            f"Links on page: {[l[0] for l in all_links[:8]]}"
        )
        return result

    # ── Step 3: Build PDF URL — exact same as verifier.py ────────────────────
    # working: full_pdf_url = "https://internalapp.nptel.ac.in" + pdf_path
    pdf_path = certificate_link["href"]
    logger.info(f"Step 2: raw href = {pdf_path}")

    if pdf_path.startswith("http"):
        pdf_url = pdf_path
    else:
        # urljoin with response.url (final URL after redirects) as base
        # handles all href formats:
        #   bare filename:  NPTEL24CS105S....pdf
        #   relative path:  ../../content/noc/...pdf
        #   absolute path:  /content/noc/...pdf
        from urllib.parse import urljoin
        pdf_url = urljoin(response.url, pdf_path)

    result["pdf_url"] = pdf_url
    logger.info(f"Step 2: Full PDF URL → {pdf_url}")

    # ── Step 4: Download PDF ──────────────────────────────────────────────────
    logger.info("Step 3: Downloading certificate PDF...")
    tmp_path = None
    try:
        pdf_response = requests.get(pdf_url, headers=HEADERS, timeout=30)
        logger.info(f"Step 3: HTTP {pdf_response.status_code}  size={len(pdf_response.content)} bytes")

        if not pdf_response.ok:
            result["detail"] = f"PDF download failed (HTTP {pdf_response.status_code})."
            return result

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_response.content)
            tmp_path = tmp.name
        logger.info("Step 3: PDF saved")

    except Exception as e:
        logger.info(f"Step 3 ERROR: {e}")
        result["detail"] = f"PDF download error: {e}"
        return result

    # ── Step 5: OCR ───────────────────────────────────────────────────────────
    try:
        logger.info("Step 4: Running OCR on official certificate PDF...")
        ocr = extract_text(tmp_path)
        logger.info(f"Step 4: OCR method={ocr['method']}  success={ocr['success']}  chars={len(ocr['text'])}")

        if not ocr["success"] or not ocr["text"].strip():
            result["detail"] = f"PDF downloaded but OCR produced no text. {ocr['detail']}"
            return result

        result["text"]       = ocr["text"]
        result["ocr_method"] = ocr["method"]
        result["success"]    = True
        result["detail"]     = f"Official PDF fetched & OCR'd via {ocr['method']}. {len(ocr['text'])} chars."
        result["fields"]     = _extract_fields(ocr["text"], pdf_url)
        logger.info(f"Step 4: Fields: {list(result['fields'].keys())}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    result["steps"] = steps
    return result


def _extract_fields(text: str, pdf_url: str) -> dict:
    """
    Extract exactly the 5 scored fields from real NPTEL certificate layout:

    "This certificate is awarded to"
    MOHAMED MUZAMMIL M                      ← candidate_name
    "for successfully completing the course"
    Programming in Java                     ← course_name
    Jul-Oct 2024  (12 week course)          ← course_duration / issue_date
    Roll No: NPTEL24CS105S1233103512        ← roll_or_cert_id
    """
    fields = {}
    patterns = {
        "candidate_name": [
            r"(?:This\s+certificate\s+is\s+awarded\s+to\s*\n\s*)([A-Z][A-Z\s\.]{2,50}?)(?:\s*\n)",
            r"(?:awarded\s+to\s*\n\s*)([A-Z][A-Z\s\.]{2,50}?)(?:\s*\n)",
            r"(?:certif(?:y|ied)\s+that\s+)([\w\s\.]{3,50}?)(?:\s+has|\n)",
        ],
        "course_name": [
            r"(?:for\s+successfully\s+completing\s+the\s+course\s*\n\s*)([^\n]+)",
            r"(?:completing\s+the\s+course\s*\n\s*)([^\n]+)",
            r"(?:course\s+on\s+[\"']?)([\w\s,\-&:\/]+?)(?:[\"']?\s+conducted|\n|$)",
        ],
        "course_duration": [
            r"\((\d+\s*week(?:s)?\s*course)\)",
        ],
        "roll_or_cert_id": [
            r"Roll\s+No[:\s]+\s*(NPTEL[\w]+)",
            r"\b(NPTEL\d{2}[A-Z]{2}\d+[A-Z]\d+)\b",
            r"Roll\s+No[:\s]+([\w\-]{6,})",
        ],
        "issue_date": [
            r"\b(Jan(?:uary)?[\-\u2013]Apr(?:il)?\s*20\d{2})\b",
            r"\b(Jul(?:y)?[\-\u2013]Oct(?:ober)?\s*20\d{2})\b",
            r"(?:date\s+of\s+issue\s*[:\-]\s*)([\w\s,\/\-]+?\d{4})",
        ],
    }

    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                val = re.sub(r"\s+", " ", m.group(1).strip())
                if val and len(val) > 1:
                    fields[field] = val
                    break

    # ── Positional fallbacks — real NPTEL PDF text layout ────────────────────
    # Real NPTEL PDFs render decorative text as images, so OCR gives bare values.
    # Name = first all-caps line; Course = text after "(N week course)"
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if "candidate_name" not in fields:
        for line in lines:
            if (re.match(r'^[A-Z][A-Z\s\.]{4,50}$', line)
                    and not line.startswith("NPTEL")
                    and not re.search(r'\d{4}', line)):
                fields["candidate_name"] = line
                break

    if "course_name" not in fields:
        m = re.search(r'\(\d+\s*week\s*course\)\s*([\w][\w\s,\-&:]+?)(?:\s*$|\n)',
                    text, re.IGNORECASE | re.MULTILINE)
        if m:
            fields["course_name"] = re.sub(r"\s+", " ", m.group(1).strip())

    if "course_duration" in fields and "issue_date" not in fields:
        fields["issue_date"] = fields["course_duration"]

    if "roll_or_cert_id" not in fields:
        m = re.search(r"(NPTEL\d{2}[A-Z]{2}\d+[A-Z]\d+)", pdf_url, re.IGNORECASE)
        if m:
            fields["roll_or_cert_id"] = m.group(1).upper()

    return fields
