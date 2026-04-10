"""
NPTEL Fetcher — Global Anchor-Based Verifier
"""

import re
import os
import logging
import tempfile
import requests
from bs4 import BeautifulSoup

# Assuming this is your local OCR module
from services.ocr_engine import extract_text 

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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
    def log(msg): logging.info(msg); steps.append(msg)

    result = {
        "success": False, "text": "", "fields": {}, "url": url,
        "pdf_url": "", "ocr_method": "none", "detail": "", "steps": steps,
    }

    # ── Step 1: Fetch QR URL ─────────────────────────────────────
    log(f"Step 1: Fetching NPTEL page: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        log(f"Step 1: HTTP {response.status_code}  final URL: {response.url}")
        if not response.ok:
            result["detail"] = f"Failed to load NPTEL page (HTTP {response.status_code})."
            return result
    except Exception as e:
        log(f"Step 1 ERROR: {e}")
        result["detail"] = f"Could not connect to NPTEL: {e}"
        return result

    # ── Step 2: Parse HTML ───────────────────────────────────────
    log("Step 2: Parsing page — looking for 'Course Certificate' button...")
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
        result["detail"] = "Could not find 'Course Certificate' button."
        return result

    # ── Step 3: Build PDF URL ────────────────────────────────────
    pdf_path = certificate_link["href"]
    if pdf_path.startswith("http"):
        pdf_url = pdf_path
    else:
        from urllib.parse import urljoin
        pdf_url = urljoin(response.url, pdf_path)

    result["pdf_url"] = pdf_url
    log(f"Step 2: Full PDF URL → {pdf_url}")

    # ── Step 4: Download PDF ─────────────────────────────────────
    log("Step 3: Downloading certificate PDF...")
    tmp_path = None
    try:
        pdf_response = requests.get(pdf_url, headers=HEADERS, timeout=30)
        log(f"Step 3: HTTP {pdf_response.status_code} size={len(pdf_response.content)}")

        if not pdf_response.ok:
            result["detail"] = f"PDF download failed (HTTP {pdf_response.status_code})."
            return result

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_response.content)
            tmp_path = tmp.name

    except Exception as e:
        log(f"Step 3 ERROR: {e}")
        result["detail"] = f"PDF download error: {e}"
        return result

    # ── Step 5: OCR and Extraction ───────────────────────────────
    try:
        log("Step 4: Running Extraction...")
        ocr = extract_text(tmp_path)

        if not ocr["success"] or not ocr["text"].strip():
            result["detail"] = "Extraction failed."
            return result

        text = ocr["text"]
        result["text"] = text
        result["ocr_method"] = ocr["method"]
        result["success"] = True
        
        # Extract the fields
        result["fields"] = _extract_fields(text, pdf_url)
        log(f"Step 4: Extracted fields → {result['fields']}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return result


# ───────────────── FIELD EXTRACTION (HYBRID LOGIC) ─────────────────

def _extract_fields(text: str, pdf_url: str = "") -> dict:
    fields = {}
    
    # Clean lines: remove empty lines and strip whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # ── 1. Line-by-Line Anchors (For Relational Data) ──
    for i, line in enumerate(lines):
        lower_line = line.lower()

        # Helper function to handle both single-line and multi-line text outputs
        def get_value_after(anchor):
            parts = re.split(re.escape(anchor), line, flags=re.IGNORECASE)
            if len(parts) > 1:
                remainder = parts[1].strip()
                remainder = re.sub(r'^[:\-]\s*', '', remainder)
                if len(remainder) > 2:
                    return remainder
            if i + 1 < len(lines):
                return lines[i + 1].strip()
            return None

        # Candidate Name
        if "awarded to" in lower_line and "candidate_name" not in fields:
            val = get_value_after("awarded to")
            if val: 
                fields["candidate_name"] = val

        # Course Name
        if "completing the course" in lower_line and "course_name" not in fields:
            val = get_value_after("completing the course")
            if val: 
                fields["course_name"] = val


    # ── 2. Global Pattern Searches (For Standalone Data) ──
    # Flattening the text bypasses arbitrary newlines injected by digital PDF parsers
    flat_text = re.sub(r'\s+', ' ', text)

    # Roll Number
    m_roll = re.search(r"(NPTEL[A-Z0-9]{10,})", flat_text, re.IGNORECASE)
    if m_roll:
        fields["roll_or_cert_id"] = m_roll.group(1).upper()
    elif pdf_url:
        m_url = re.search(r"(NPTEL[A-Z0-9]{10,})", pdf_url, re.IGNORECASE)
        if m_url:
            fields["roll_or_cert_id"] = m_url.group(1).upper()

    # Course Duration
    m_duration = re.search(r"(\d+\s*week(?:s)?(?:\s*course)?)", flat_text, re.IGNORECASE)
    if m_duration:
        fields["course_duration"] = m_duration.group(1).lower()

    # Issue Date / Session Timeline
    # Matches formats like: "Jan-Feb 2025", "Jan - Feb 2025", "July-Oct 2024", "Jan 2025"
    month_regex = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    date_pattern = rf"({month_regex}\s*[-–—_]*\s*(?:{month_regex})?\s*20\d{{2}})"
    
    m_date = re.search(date_pattern, flat_text, re.IGNORECASE)
    if m_date:
        raw_date = m_date.group(1)
        # Normalize dashes (e.g., "Jan - Feb" -> "Jan-Feb")
        clean_date = re.sub(r'\s*[-–—_]+\s*', '-', raw_date)
        # Normalize spacing
        clean_date = re.sub(r'\s+', ' ', clean_date)
        fields["issue_date"] = clean_date.title()

    return fields