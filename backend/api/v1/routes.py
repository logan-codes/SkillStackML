"""
api/v1/routes.py
────────────────
FastAPI router for API v1.

Endpoints:
    GET  /api/v1/                    — health check
    GET  /api/v1/workflows           — list all registered workflows + metadata
    POST /api/v1/verify/{provider}   — verify a certificate for the given provider
"""

import os
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Path
from fastapi.responses import JSONResponse
from core.registry  import get_workflow, list_workflows
from core.logger    import get_logger
from core.config    import settings
from utils.file_utils import save_temp_file

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Certificate Verification"])

SUPPORTED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/jpg",
}


# ── GET / ────────────────────────────────────────────────────
@router.get("/", summary="Health check")
def health():
    """Returns API status and list of active providers."""
    return {
        "status":    "running",
        "version":   "1.0",
        "providers": list(list_workflows().keys()),
    }


# ── GET /workflows ───────────────────────────────────────────
@router.get("/workflows", summary="List all registered workflows")
def get_workflows():
    """
    Returns metadata for every registered workflow including
    provider name, display name, version, and required fields.
    """
    return list_workflows()


# ── POST /verify/{provider} ──────────────────────────────────
@router.post("/verify/{provider}", summary="Verify a certificate")
async def verify_certificate(
    provider: str = Path(
        ...,
        description="Platform provider: nptel | codetantra | coursera | udemy",
        example="coursera",
    ),
    file: UploadFile = File(..., description="Certificate file — PDF, JPG, or PNG"),
):
    """
    Verify an uploaded certificate using the specified platform's pipeline.

    - **provider**: One of `nptel`, `codetantra`, `coursera`, `udemy`
    - **file**: The certificate to verify (PDF, JPG, PNG — max 10 MB)

    Returns a standardised JSON result with:
    - `is_genuine`: bool
    - `message`: human-readable verdict
    - `field_breakdown`: per-field comparison results
    - `data`: raw extracted fields from both uploaded and official sources
    """
    # ── Validate file type ───────────────────────────────────
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Accepted: PDF, JPG, PNG.",
        )

    # ── Validate file size ───────────────────────────────────
    #read the file contents into memory (all workflows currently require it, even NPTEL which needs a temp file path)
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_MB} MB.",
        )

    # ── Resolve workflow ─────────────────────────────────────
    try:
        workflow = get_workflow(provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    logger.info(f"[API] POST /verify/{provider}  file={file.filename}  size={len(contents)} bytes")

    # ── Build payload ────────────────────────────────────────
    # NPTEL needs a temp file path; others work with bytes in-memory
    if provider == "nptel":
        tmp_path = save_temp_file(contents, file.filename or "cert.png")
        payload = {
            "path": tmp_path,
            # verf_url can be passed as a form field in future — currently empty
            "verf_url": "",
        }
    else:
        payload = {
            "contents":     contents,
            "content_type": file.content_type,
        }

    # ── Validate payload ─────────────────────────────────────
    ok, err = workflow.validate(payload)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # ── Run workflow ─────────────────────────────────────────
    try:
        # NPTEL is synchronous (uses sync OCR + requests)
        # Coursera / Udemy use asyncio.to_thread for blocking Groq calls
        if provider == "nptel":
            result = await asyncio.to_thread(workflow.process, payload)
        else:
            result = await asyncio.to_thread(workflow.process, payload)

        logger.info(f"[API] {provider} workflow complete")
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[API] Workflow error for {provider}: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")
