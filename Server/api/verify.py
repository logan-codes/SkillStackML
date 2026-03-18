import os
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from services.ocr_engine    import extract_text
from services.qr_scanner    import scan_qr
from services.nptel_fetcher import fetch_nptel
from services.comparator    import extract_key_fields

from schema.verify import VerifyRequest

from core.logger import logger

from utils.save import _save
from utils.compare import _strict_compare

router = APIRouter(prefix="/verify")

@router.post("/")
async def verify(req: VerifyRequest = Depends()):
    logger.info(f"[/verify] file={req.file.filename}  manual_url={repr(req.verification_url)}")

    content  = await req.file.read()
    tmp_path = _save(content, req.file.filename or "cert.png")

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
        # Step 1 — OCR uploaded certificate
        uploaded_ocr = extract_text(tmp_path)
        response["uploaded_ocr"] = uploaded_ocr
        print(f"[step1] OCR method={uploaded_ocr['method']}  chars={len(uploaded_ocr['text'])}")

        # Step 2 — Scan QR code
        qr = scan_qr(tmp_path)
        response["qr"] = qr
        print(f"[step2] QR found={qr['found']}  url={qr['url'][:80] if qr['url'] else '(none)'}")

        # Determine NPTEL URL to use
        nptel_url = None
        if req.verification_url and req.verification_url.strip():
            nptel_url = req.verification_url.strip()
            if not nptel_url.startswith("http"):
                nptel_url = "https://" + nptel_url
            print(f"[step2] Using manual_url: {nptel_url}")
        elif qr["found"] and qr["url"]:
            nptel_url = qr["url"]
            print(f"[step2] Using QR URL: {nptel_url}")

        if not nptel_url:
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
            official = fetch_nptel(nptel_url)
            response["official"] = official
            print(f"[step3] official success={official['success']}  chars={len(official['text'])}")

            # Step 4 — Strict compare
            u_fields = extract_key_fields(uploaded_ocr["text"])
            o_fields = {**extract_key_fields(official["text"]), **official.get("fields", {})}

            cmp = _strict_compare(uploaded_ocr, official["text"], u_fields, o_fields)
            response["comparison"]      = cmp
            response["uploaded_fields"] = u_fields
            response["official_fields"] = o_fields

    except Exception as e:
        import traceback; traceback.print_exc()
        response["error"] = str(e)
        response["comparison"]["verification_status"] = "ERROR"
        response["comparison"]["reason"] = str(e)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return JSONResponse(content=response)
