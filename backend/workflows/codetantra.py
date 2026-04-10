"""
workflows/codetantra.py
───────────────────────
CodeTantra Certificate Verification Workflow.

Pipeline:
    1. Extract text from uploaded PDF/image via PyMuPDF + Tesseract OCR
    2. Parse Certificate ID (pattern: CT####-xxx-xxx), name, course, date
    3. Scrape Sathyabama CodeTantra portal with 3-retry / increasing-timeout logic
    4. Parse same fields from portal response
    5. Compare all fields — ALL must match → GENUINE, any failure → FAKE
"""

import re
import io
import os
import time
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
import fitz  # PyMuPDF

from schema.workflow import Workflow
from core.logger     import get_logger

logger = get_logger(__name__)

PORTAL_BASE_URL = "https://sathyabama.codetantra.com/cert/certificate.jsp"


class CodeTantraWorkflow(Workflow):
    """Verification workflow for CodeTantra / Sathyabama certificates."""

    def __init__(self):
        super().__init__(
            provider   = "codetantra",
            name       = "CodeTantra Workflow",
            req_fields = ["contents", "content_type"],
        )

    # ── Helpers ─────────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        """
        Normalize text for exact comparison:
        - Collapse all whitespace variants (\xa0, \t, \n, zero-width) to single space
        - Remove invisible unicode characters
        - Lowercase + strip punctuation edges
        """
        if not text:
            return ""
        t = str(text)
        # Remove invisible unicode characters (zero-width space, BOM, soft-hyphen etc.)
        t = re.sub(r'[\u200b\u200c\u200d\ufeff\u00ad\u2060]', '', t)
        # Replace non-breaking spaces and whitespace variants with regular space
        t = re.sub(r'[\xa0\t\r\n]+', ' ', t)
        # Collapse multiple spaces into one
        t = re.sub(r' +', ' ', t)
        # Strip, lowercase, remove edge punctuation
        t = t.strip().lower().strip('.,;:')
        return t

    def _compare_field(self, a: str, b: str, field: str) -> bool:
        """
        Compare two field values after normalization.
        Logs both repr() values so hidden characters are visible in terminal.
        """
        na = self._normalize(a)
        nb = self._normalize(b)
        match = na == nb
        logger.info(f"  [{field}] PDF    repr: {repr(na)}")
        logger.info(f"  [{field}] PORTAL repr: {repr(nb)}")
        logger.info(f"  [{field}] match : {match}")
        return match

    def _extract_details(self, text: str, source: str = "") -> dict:
        """
        Extract certificate_id, name, course, date from raw text.
        Tries multiple regex patterns per field to handle both
        PDF text layout and portal HTML text layout.
        """
        details = {"certificate_id": None, "name": None, "course": None, "date": None}

        # ── Certificate ID ───────────────────────────────────
        # Pattern: CT2024-ABCD-1234  or  CT####-xxx-xxx
        id_match = re.search(r'(CT\d{4}-[a-zA-Z0-9]+-[a-zA-Z0-9]+)', text)
        if id_match:
            details["certificate_id"] = id_match.group(1).strip()

        # ── Name ─────────────────────────────────────────────
        # PDF:    "certify that JOHN DOE ("
        # Portal: "certify that JOHN DOE has" or "certify that JOHN DOE successfully"
        name_patterns = [
            r'certify\s+that\s+([A-Za-z\s]+?)\s*\(',           # PDF: name before (
            r'certify\s+that\s+([A-Za-z\s]+?)\s+has\b',        # Portal: name before "has"
            r'certify\s+that\s+([A-Za-z\s]+?)\s+successfully',  # Portal: name before "successfully"
            r'awarded\s+to\s+([A-Za-z\s]+?)\s*[(\n]',          # alternative phrasing
        ]
        for pat in name_patterns:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                name = m.group(1).replace('\n', ' ').strip()
                if len(name) > 1:
                    details["name"] = name
                    break

        # ── Course ───────────────────────────────────────────
        # PDF:    "titled COURSE NAME from"
        # Portal: "titled COURSE NAME from" or "course titled COURSE NAME"
        course_patterns = [
            r'titled\s+(.*?)\s+from\b',
            r'course\s+titled\s+(.*?)\s+from\b',
            r'titled\s+(.*?)\s+conducted\b',
            r'course\s+on\s+["\']?(.*?)["\']?\s+(?:from|conducted|during)',
        ]
        for pat in course_patterns:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                course = m.group(1).replace('\n', ' ').strip()
                if len(course) > 1:
                    details["course"] = course
                    break

        # ── Date ─────────────────────────────────────────────
        # PDF/Portal: "Date: Jan 01, 2024" or "Date: 01 Jan 2024"
        date_patterns = [
            r'Date[:\s]+([A-Za-z]{3}\s*\d{1,2},?\s*\d{4})',
            r'Date[:\s]+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})',
            r'Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        ]
        for pat in date_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                details["date"] = m.group(1).replace('\n', ' ').strip()
                break

        # ── Debug — print exactly what was extracted ─────────
        logger.info(f"[{source}] Extracted fields:")
        for k, v in details.items():
            logger.info(f"  {k:20s} = {repr(v)}")

        return details

    # ── Portal scraper with retry ───────────────────────────

    def _scrape_portal(self, cert_id: str) -> str | None:
        """
        Fetch the CodeTantra certificate page for the given ID.
        Retries 3 times with increasing timeouts (10s, 20s, 30s).
        Returns extracted text or None if all attempts fail.
        """
        url = f"{PORTAL_BASE_URL}?certId={cert_id}"
        timeouts = [10, 20, 30]

        for attempt in range(1, 4):
            try:
                logger.info(f"[Scraper] Attempt {attempt}/3 — {url} (timeout={timeouts[attempt-1]}s)")
                resp = requests.get(url, timeout=timeouts[attempt - 1])

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=' ', strip=True)
                    if len(text.strip()) > 20:
                        logger.info(f"[Scraper] Success on attempt {attempt} — {len(text)} chars")
                        # Debug: print raw portal text to see exact layout
                        logger.info(f"[Scraper] Raw portal text (first 1000 chars):\n{text[:1000]}")
                        return text
                    logger.warning(f"[Scraper] Attempt {attempt} — empty content, retrying")
                else:
                    logger.warning(f"[Scraper] Attempt {attempt} — HTTP {resp.status_code}")

            except requests.Timeout:
                logger.warning(f"[Scraper] Attempt {attempt} — timeout after {timeouts[attempt-1]}s")
            except requests.ConnectionError:
                logger.warning(f"[Scraper] Attempt {attempt} — connection error")
            except Exception as e:
                logger.error(f"[Scraper] Attempt {attempt} — unexpected error: {e}")

            if attempt < 3:
                time.sleep(2)

        logger.error("[Scraper] All 3 attempts failed")
        return None

    # ── Text extraction ──────────────────────────────────────

    def _extract_text(self, contents: bytes, content_type: str) -> str:
        """Extract text from PDF or image using PyMuPDF + Tesseract fallback."""
        extracted = ""
        if content_type == "application/pdf":
            pdf_doc = fitz.open(stream=contents, filetype="pdf")
            for page in pdf_doc:
                page_text = page.get_text()
                if len(page_text.strip()) < 15:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_text = pytesseract.image_to_string(img)
                extracted += page_text + "\n"
        elif content_type in ("image/jpeg", "image/png", "image/jpg"):
            image = Image.open(io.BytesIO(contents))
            extracted = pytesseract.image_to_string(image)

        # Debug: print raw PDF text to see exact layout
        logger.info(f"[PDF] Raw extracted text (first 1000 chars):\n{extracted[:1000]}")
        return extracted

    # ── Process ─────────────────────────────────────────────

    def process(self, payload: dict) -> dict:
        """
        Verify a CodeTantra certificate.

        Required payload keys:
            contents     (bytes) — raw file bytes
            content_type (str)   — MIME type

        Returns:
            Standard response dict.
        """
        contents     = payload["contents"]
        content_type = payload["content_type"]

        # ── Step 1: Extract text from uploaded file ──────────
        logger.info("CodeTantra workflow started")
        logger.info("Step 1 — OCR extraction")
        extracted_text = self._extract_text(contents, content_type)
        logger.info(f"Extracted {len(extracted_text)} chars")

        # ── Step 2: Parse uploaded fields ────────────────────
        logger.info("Step 2 — Field extraction from PDF")
        uploaded = self._extract_details(extracted_text, source="PDF")
        cert_id = uploaded.get("certificate_id")

        if not cert_id:
            return {
                "status":     "error",
                "is_genuine": False,
                "message":    "Could not find a valid Certificate ID in the uploaded document.",
                "field_breakdown": {},
                "data": {"uploaded_data": uploaded, "official_data": {}},
            }

        # ── Step 3: Scrape official portal ───────────────────
        logger.info(f"Step 3 — Portal scrape for cert_id={cert_id}")
        official_text = self._scrape_portal(cert_id)

        if not official_text:
            return {
                "status":     "error",
                "is_genuine": False,
                "message":    "Failed to reach the official portal after 3 attempts. Please try again.",
                "field_breakdown": {},
                "data": {"uploaded_data": uploaded, "official_data": {}},
            }

        # ── Step 4: Parse official fields ────────────────────
        logger.info("Step 4 — Parse official fields from portal")
        official = self._extract_details(official_text, source="PORTAL")

        # ── Step 5: Exact comparison ─────────────────────────
        logger.info("Step 5 — Exact field comparison")
        logger.info(f"  name   PDF    : {repr(self._normalize(uploaded['name']))}")
        logger.info(f"  name   PORTAL : {repr(self._normalize(official['name']))}")
        logger.info(f"  course PDF    : {repr(self._normalize(uploaded['course']))}")
        logger.info(f"  course PORTAL : {repr(self._normalize(official['course']))}")
        logger.info(f"  date   PDF    : {repr(self._normalize(uploaded['date']))}")
        logger.info(f"  date   PORTAL : {repr(self._normalize(official['date']))}")

        name_match   = self._compare_field(uploaded["name"],   official["name"],   "name")
        course_match = self._compare_field(uploaded["course"], official["course"], "course")
        date_match   = self._compare_field(uploaded["date"],   official["date"],   "date")

        field_breakdown = {
            "certificate_id": {
                "uploaded": uploaded["certificate_id"],
                "official": official["certificate_id"],
                "result":   True,  # cert_id used to fetch portal — already confirmed
            },
            "name": {
                "uploaded": uploaded["name"],
                "official": official["name"],
                "result":   name_match,
            },
            "course": {
                "uploaded": uploaded["course"],
                "official": official["course"],
                "result":   course_match,
            },
            "date": {
                "uploaded": uploaded["date"],
                "official": official["date"],
                "result":   date_match,
            },
        }

        is_genuine = all(v["result"] for v in field_breakdown.values())
        logger.info(f"Verdict: {'GENUINE' if is_genuine else 'FAKE'}")

        return {
            "status":           "success",
            "certificate_id":   cert_id,
            "is_genuine":       is_genuine,
            "message":          "Valid Certificate" if is_genuine else "Tampered / Fake Certificate Detected",
            "field_breakdown":  field_breakdown,
            "data": {
                "uploaded_data": uploaded,
                "official_data": official,
            },
        }


# ── Module-level exports ─────────────────────────────────────
_instance = CodeTantraWorkflow()
METADATA  = _instance.METADATA
validate  = _instance.validate
process   = _instance.process
