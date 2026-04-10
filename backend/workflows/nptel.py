"""
workflows/nptel.py
──────────────────
NPTEL Certificate Verification Workflow.

Pipeline:
    1. OCR uploaded certificate  (OpenCV + Tesseract → Pillow + Tesseract → PyMuPDF native)
    2. QR scan                   (pyzbar → OpenCV → preprocessed)
    3. Fetch NPTEL portal page   (requests → find "Course Certificate" button → download PDF)
    4. OCR official PDF
    5. Extract 5 fields from both sides
    6. Strict weighted comparison (name 30%, course 25%, roll_id 20%, duration 15%, date 10%)
    7. ALL fields must match → GENUINE, any failure → FAKE
"""

import os
from schema.workflow import Workflow
from services.ocr_engine    import extract_text
from services.qr_scanner    import scan_qr
from services.nptel_fetcher import fetch_nptel
from services.comparator    import extract_key_fields
from utils.compare          import _strict_compare
from core.logger            import get_logger

logger = get_logger(__name__)


class NPTELWorkflow(Workflow):
    """Verification workflow for NPTEL certificates."""

    def __init__(self):
        super().__init__(
            provider     = "nptel",
            name         = "NPTEL Workflow",
            req_fields   = ["path"],          # verf_url is optional
        )

    def process(self, payload: dict) -> dict:
        """
        Verify an NPTEL certificate.

        Required payload keys:
            path     (str) — absolute path to the uploaded temp file
            verf_url (str) — optional manual NPTEL verification URL

        Returns:
            Standard response dict with comparison results.
        """
        path     = payload["path"]
        verf_url = payload.get("verf_url", "")

        response = {
            "uploaded_ocr": {"text":"","method":"none","success":False,"detail":""},
            "qr":           {"found":False,"url":"","data":"","method":"none","detail":""},
            "official":     {"text":"","fields":{},"url":"","pdf_url":"","success":False,
                             "detail":"","ocr_method":"none","steps":[]},
            "comparison":   {"can_compare":False,"reason":"Processing...","score":0.0,
                             "field_comparison":{},"verification_status":"UNKNOWN"},
            "error": None,
        }

        try:
            logger.info("NPTEL workflow started")

            # ── Step 1: OCR uploaded certificate ────────────────
            logger.info("Step 1 — OCR extraction")
            uploaded_ocr = extract_text(path)
            response["uploaded_ocr"] = uploaded_ocr
            logger.info(f"OCR method={uploaded_ocr['method']}  chars={len(uploaded_ocr['text'])}")

            # ── Step 2: QR scan ──────────────────────────────────
            logger.info("Step 2 — QR scan")
            qr = scan_qr(path)
            response["qr"] = qr
            logger.info(f"QR found={qr['found']}  url={qr['url'][:80] if qr['url'] else '(none)'}")

            # ── Determine NPTEL URL ──────────────────────────────
            if verf_url and verf_url.strip():
                if not verf_url.startswith("http"):
                    verf_url = "https://" + verf_url
                logger.info(f"Using manual URL: {verf_url}")
            elif qr["found"] and qr["url"]:
                verf_url = qr["url"]
                logger.info(f"Using QR URL: {verf_url}")

            if not verf_url:
                response["comparison"] = {
                    "can_compare":         False,
                    "score":               0.0,
                    "field_comparison":    {},
                    "verification_status": "NO_QR_FOUND",
                    "reason": (
                        "No QR code detected in the certificate. "
                        "Ensure the image is clear and well-lit. "
                        "You can also enter the NPTEL verification URL manually."
                    ),
                }
                return response

            # ── Step 3: Fetch official NPTEL PDF + OCR ───────────
            logger.info(f"Step 3 — Fetch NPTEL page: {verf_url}")
            official = fetch_nptel(verf_url)
            response["official"] = official
            logger.info(f"Official success={official['success']}  chars={len(official['text'])}")

            # ── Step 4: Extract fields from both sides ───────────
            logger.info("Step 4 — Field extraction & comparison")
            u_fields = extract_key_fields(uploaded_ocr["text"])
            o_fields = {**extract_key_fields(official["text"]), **official.get("fields", {})}

            # ── Step 5: Strict comparison ────────────────────────
            cmp = _strict_compare(uploaded_ocr, official["text"], u_fields, o_fields)
            response["comparison"]      = cmp
            response["uploaded_fields"] = u_fields
            response["official_fields"] = o_fields
            logger.info(f"Verdict: {cmp['verification_status']}  score={cmp['score']:.3f}")

        except Exception as e:
            import traceback; traceback.print_exc()
            logger.error(f"NPTEL workflow error: {e}")
            response["error"] = str(e)
            response["comparison"]["verification_status"] = "ERROR"
            response["comparison"]["reason"] = str(e)

        finally:
            if os.path.exists(path):
                os.unlink(path)

        return response


# ── Module-level exports so registry can import directly ────
_instance = NPTELWorkflow()
METADATA  = _instance.METADATA
validate  = _instance.validate
process   = _instance.process
