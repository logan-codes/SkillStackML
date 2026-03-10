from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response as RawResponse
import uvicorn, tempfile, os
from typing import Optional

from ocr_engine    import extract_text
from qr_scanner    import scan_qr
from nptel_fetcher import fetch_nptel
from comparator    import compare_certificates, extract_key_fields
import browser_fetcher as bf

app = FastAPI(title="CertVerify NPTEL v2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def _save(content: bytes, filename: str) -> str:
    ext = os.path.splitext(filename or "cert.png")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"}:
        ext = ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
        f.write(content); return f.name


def _strict_compare(uploaded_ocr, official_text, u_fields, o_fields):
    u_text = (uploaded_ocr.get("text") or "").strip()
    o_text = (official_text or "").strip()

    if not uploaded_ocr.get("success") or not u_text:
        return {"can_compare": False, "score": 0.0, "field_comparison": {},
                "verification_status": "OCR_FAILED",
                "reason": "Uploaded certificate OCR produced no text. Install Tesseract."}
    if not o_text:
        return {"can_compare": False, "score": 0.0, "field_comparison": {},
                "verification_status": "NO_OFFICIAL_TEXT",
                "reason": "No text retrieved from official NPTEL certificate PDF."}

    cmp     = compare_certificates(u_fields, o_fields, u_text, o_text)
    score   = cmp["score"]
    verdict = cmp.get("verdict", "UNVERIFIED")
    reason  = cmp.get("verdict_reason", "")
    print(f"[compare] score={score}  verdict={verdict}")

    # GENUINE → VALID, FAKE → FAKE, UNVERIFIED → UNKNOWN
    status_map = {"GENUINE": "VALID", "FAKE": "FAKE", "UNVERIFIED": "UNKNOWN"}

    return {
        "can_compare":         True,
        "reason":              reason,
        "score":               score,
        "field_comparison":    cmp["field_matches"],
        "field_matches":       cmp["field_matches"],
        "failed_fields":       cmp.get("failed_fields", []),
        "not_found":           cmp.get("not_found", []),
        "verification_status": status_map.get(verdict, "UNKNOWN"),
    }


@app.get("/")
def root(): return {"status": "running", "version": "2.0"}

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/screenshot")
def screenshot(url: str):
    if not bf.is_available():
        return JSONResponse({"error": "Playwright not installed",
                             "fix": "pip install playwright && playwright install chromium"}, status_code=503)
    try:
        r = bf.fetch_with_browser(url)
        return RawResponse(content=r["screenshot"], media_type="image/png")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/verify")
async def verify(
    file: UploadFile = File(...),
    manual_url: Optional[str] = Form(default=None),
):
    print(f"\n{'='*55}")
    print(f"[/verify] file={file.filename}  manual_url={repr(manual_url)}")

    content  = await file.read()
    tmp_path = _save(content, file.filename or "cert.png")

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
        if manual_url and manual_url.strip():
            nptel_url = manual_url.strip()
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
