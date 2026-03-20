"""
main.py
───────
CertVerify — Multi-Platform Certificate Verification API
FastAPI application entry point.

Run via:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Or via start.bat (Windows) which handles venv + deps automatically.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config  import settings
from core.logger  import get_logger
from api.v1.routes import router as v1_router

logger = get_logger(__name__)

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title       = "CertVerify — Multi-Platform Certificate Verification",
    description = (
        "Unified API for verifying certificates from NPTEL, CodeTantra, "
        "Coursera, and Udemy using AI-powered and OCR-based pipelines."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS middleware ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origins_list,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ─────────────────────────────────────────────────
app.include_router(v1_router)

# ── Root redirect ────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "message":  "CertVerify API is running.",
        "docs":     "/docs",
        "version":  "1.0.0",
        "providers": ["nptel", "codetantra", "coursera", "udemy"],
    }


# ── Startup / shutdown events ────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("=" * 55)
    logger.info("  CertVerify API  v1.0.0  starting up")
    logger.info(f"  Host : {settings.HOST}:{settings.PORT}")
    logger.info(f"  Docs : http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 55)


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("CertVerify API shutting down.")


# ── Dev runner ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host    = settings.HOST,
        port    = settings.PORT,
        reload  = settings.RELOAD,
        log_level = settings.LOG_LEVEL,
    )
