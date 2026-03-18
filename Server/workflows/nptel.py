from core.logger import get_logger
from schema.workflow import Workflow
from services.ocr_engine import extract_text
from services.qr_scanner import scan_qr

from services.ocr_engine    import extract_text
from services.qr_scanner    import scan_qr
from services.nptel_fetcher import fetch_nptel
from services.comparator    import extract_key_fields

from utils.compare import _strict_compare

import os

logger=get_logger(__name__)

class NPTEL(Workflow):
    def __init__(self):
        super().__init__("nptel", "NPTEL Workflow", ["path","verf_url"])
        
    def process(self, path: str, verf_url:str):
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
            logger.info("NPTEL Workflow has started.")
            ocr_text = extract_text(path)
            logger.info("OCR extraction done")
            qr = scan_qr(path)
            logger.info("QR Scanned")
            if verf_url and verf_url.strip():
                if not verf_url.startswith("http"):
                    verf_url = "https://" + verf_url
            elif qr["found"] and qr["url"]:
                verf_url = qr["url"]
            if not verf_url:
                response["comparison"] = {
                    "can_compare": False, "score": 0.0, "field_comparison": {},
                    "verification_status": "NO_QR_FOUND",
                    "reason": (
                        "No QR code detected in the certificate. "
                        "Ensure the image is clear and well-lit. "
                        "You can also enter the NPTEL verification URL manually."
                    ),
                }
            else:
                # Step 3 — Fetch NPTEL page → find Course Certificate button → download PDF → OCR
                official = fetch_nptel(verf_url)
                response["official"] = official
                print(f"[step3] official success={official['success']}  chars={len(official['text'])}")

                # Step 4 — Strict compare
                u_fields = extract_key_fields(ocr_text["text"])
                o_fields = {**extract_key_fields(official["text"]), **official.get("fields", {})}

                cmp = _strict_compare(ocr_text, official["text"], u_fields, o_fields)
                response["comparison"]      = cmp
                response["uploaded_fields"] = u_fields
                response["official_fields"] = o_fields

        except Exception as e:
            import traceback; traceback.print_exc()
            response["error"] = str(e)
            response["comparison"]["verification_status"] = "ERROR"
            response["comparison"]["reason"] = str(e)
        finally:
            if os.path.exists(path):
                os.unlink(path)

        return response

_nptel = NPTEL()
METADATA = _nptel.METADATA
validate = _nptel.validate
process  = _nptel.process



