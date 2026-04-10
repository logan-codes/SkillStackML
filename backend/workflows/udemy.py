"""
workflows/udemy.py
──────────────────
Udemy Certificate Verification Workflow.

Pipeline:
    1. Convert uploaded PDF/image → JPEG
    2. Groq Vision AI extracts: name, course, date, certificate_id
    3. Ensure uppercase UC- prefix (critical — S3 bucket is case-sensitive)
    4. Download official image from Udemy S3 (no timestamp needed)
       → blocked: return status="retry"
    5. Vision AI reads official image
    6. AI semantic comparison: cert_id, name, course, date (4 fields)
    7. ALL fields match → GENUINE, any failure → FAKE

Key insight: S3 URL must use uppercase UC- prefix.
    WRONG: uc-0d3c6da7-...  → HTTP 403
    RIGHT: UC-0d3c6da7-...  → HTTP 200
"""

import re
import requests
import time

from schema.workflow      import Workflow
from services.groq_client import extract_with_vision, ai_compare
from utils.file_utils     import to_image_bytes, normalize_date, normalize
from core.logger          import get_logger

logger = get_logger(__name__)

# ── Groq Vision prompt for Udemy ─────────────────────────────
VISION_PROMPT = """This is a Udemy certificate image. Extract and return JSON only:
{
  "name": "recipient full name",
  "course": "course title only",
  "date": "completion date e.g. May 13, 2022",
  "certificate_id": "full cert ID e.g. UC-0d3c6da7-7366-406c-8748-03c575ce58ab"
}
Return ONLY valid JSON."""

IMG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.udemy.com/",
}


class UdemyWorkflow(Workflow):
    """Verification workflow for Udemy certificates."""

    def __init__(self):
        super().__init__(
            provider   = "udemy",
            name       = "Udemy Workflow",
            req_fields = ["contents", "content_type"],
        )

    # ── Official image download ──────────────────────────────

    def _download_official_image(self, cert_id: str) -> tuple:
        """
        Download official Udemy certificate image from S3.
        Pattern: udemy-certificate.s3.amazonaws.com/image/{UC-xxxx}.jpg
        No timestamp needed — uppercase UC- prefix is the critical requirement.

        Returns (image_bytes, image_url) or (None, url) on failure.
        """
        url = f"https://udemy-certificate.s3.amazonaws.com/image/{cert_id}.jpg"
        logger.info(f"[Official] Downloading: {url}")

        for attempt in range(1, 4):
            try:
                resp = requests.get(url, headers=IMG_HEADERS, timeout=20)
                logger.info(f"[Official] Attempt {attempt}: HTTP {resp.status_code}")
                if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
                    return resp.content, url
                time.sleep(3 * attempt)
            except Exception as e:
                logger.error(f"[Official] Error on attempt {attempt}: {e}")
                time.sleep(3 * attempt)

        return None, url

    # ── Process ─────────────────────────────────────────────

    def process(self, payload: dict) -> dict:
        """
        Verify a Udemy certificate.

        Required payload keys:
            contents     (bytes) — raw file bytes
            content_type (str)   — MIME type

        Returns:
            Standard response dict.
        """
        contents     = payload["contents"]
        content_type = payload["content_type"]

        logger.info("Udemy workflow started")

        # ── Step 1: Convert to JPEG + Vision AI ─────────────
        logger.info("Step 1 — Convert PDF/image to JPEG")
        image_bytes = to_image_bytes(contents, content_type)

        logger.info("Step 2 — Vision AI extraction on uploaded cert")
        uploaded = extract_with_vision(image_bytes, VISION_PROMPT, label="UPLOADED")
        for k in ["name", "course", "date", "certificate_id"]:
            if k not in uploaded:
                uploaded[k] = None

        # ── Ensure uppercase UC- prefix ──────────────────────
        cert_id = (uploaded.get("certificate_id") or "").strip()
        cert_id = re.sub(r'^uc-', 'UC-', cert_id, flags=re.IGNORECASE)
        uploaded["certificate_id"] = cert_id
        logger.info(f"cert_id={cert_id}")

        if not cert_id:
            return {
                "status":     "error",
                "is_genuine": False,
                "message":    "Could not extract Certificate ID from the uploaded file.",
                "field_breakdown": {},
                "data": {"uploaded_data": uploaded, "official_data": {}},
            }

        # ── Step 3: Download official image ─────────────────
        logger.info("Step 3 — Download official Udemy S3 image")
        official_bytes, image_url = self._download_official_image(cert_id)

        if not official_bytes:
            logger.warning("Official image unavailable — returning retry")
            return {
                "status":         "retry",
                "message":        "Official certificate image could not be fetched. Please try again.",
                "certificate_id": cert_id,
                "verify_url":     f"https://ude.my/{cert_id}",
                "uploaded_data":  uploaded,
            }

        # ── Step 4: Vision AI on official image ─────────────
        logger.info("Step 4 — Vision AI on official image")
        official = extract_with_vision(official_bytes, VISION_PROMPT, label="OFFICIAL")
        for k in ["name", "course", "date", "certificate_id"]:
            if k not in official:
                official[k] = None

        # ── Step 5: AI semantic comparison (4 fields) ────────
        logger.info("Step 5 — AI semantic comparison (4 fields)")

        def strict_compare(a, b, field):
            """
            Strict comparison for critical fields:
            - Exact normalize match → True immediately
            - One is substring of other → False (catches truncation by Vision AI)
            - Only call AI compare if values are genuinely different words
            """
            if not a or not b:
                return False
            na = normalize(a)
            nb = normalize(b)
            # Exact match
            if na == nb:
                logger.info(f"[{field}] exact match ✓")
                return True
            # One is a substring of the other → NOT the same (truncation)
            if na in nb or nb in na:
                logger.info(f"[{field}] substring mismatch ✗ — '{na}' vs '{nb}'")
                return False
            # Genuinely different — let AI decide
            return ai_compare(a, b, field)

        id_match     = strict_compare(uploaded.get("certificate_id"), official.get("certificate_id"), "certificate_id")
        name_match   = strict_compare(uploaded.get("name"),           official.get("name"),           "name")
        course_match = strict_compare(uploaded.get("course"),         official.get("course"),         "course")
        date_match   = normalize_date(uploaded.get("date")) == normalize_date(official.get("date"))

        is_genuine = id_match and name_match and course_match and date_match
        score = sum([id_match, name_match, course_match, date_match]) * 25
        logger.info(f"Verdict: {'GENUINE' if is_genuine else 'FAKE'}  score={score}%")

        return {
            "status":        "success",
            "is_genuine":    is_genuine,
            "overall_score": f"{score}%",
            "message":       "Valid Certificate" if is_genuine else "Tampered / Fake Certificate Detected",
            "verify_url":    f"https://ude.my/{cert_id}",
            "official_image": image_url,
            "field_breakdown": {
                "certificate_id": {"uploaded": uploaded.get("certificate_id"), "official": official.get("certificate_id"), "result": id_match},
                "name":           {"uploaded": uploaded.get("name"),           "official": official.get("name"),           "result": name_match},
                "course":         {"uploaded": uploaded.get("course"),         "official": official.get("course"),         "result": course_match},
                "date":           {"uploaded": uploaded.get("date"),           "official": official.get("date"),           "result": date_match,
                                   "normalized_uploaded": normalize_date(uploaded.get("date")),
                                   "normalized_official": normalize_date(official.get("date"))},
            },
            "data": {"uploaded_data": uploaded, "official_data": official},
        }


# ── Module-level exports ─────────────────────────────────────
_instance = UdemyWorkflow()
METADATA  = _instance.METADATA
validate  = _instance.validate
process   = _instance.process