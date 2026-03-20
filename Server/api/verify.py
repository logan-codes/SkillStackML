from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from schema.verify import VerifyRequest
from core.dispatcher import dispatch
from core.logger import logger
from utils.save import _save

router = APIRouter(prefix="/verify")

@router.post("/")
async def verify(req: VerifyRequest = Depends()):
    logger.info(f"[/verify] provider={req.provider}  file={req.file.filename}")

    content  = await req.file.read()
    tmp_path = _save(content, req.file.filename or "cert.png")

    payload = {
        "provider":           req.provider,
        "path":               tmp_path,
        "verf_url":           req.verification_url or "",
        "name":               req.name,
        "course_name":        req.course_name,
        "date_of_completion": req.date_of_completion,
    }

    result = dispatch(payload)
    return JSONResponse(content=result)
