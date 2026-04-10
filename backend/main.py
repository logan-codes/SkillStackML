"""
main.py
───────
CertVerify — Multi-Platform Certificate Verification API
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from core.config   import settings
from core.logger   import get_logger
from api.v1.routes import router as v1_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("=" * 55)
    logger.info("  CertVerify API  v1.0.0  starting up")
    logger.info(f"  Host : {settings.HOST}:{settings.PORT}")
    logger.info(f"  Docs : http://localhost:{settings.PORT}/docs")
    logger.info("=" * 55)
    yield
    # ── Shutdown (nothing needed) ─────────────────────────────


# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title       = "CertVerify — Multi-Platform Certificate Verification",
    description = "Verify certificates from NPTEL, CodeTantra, Coursera, and Udemy.",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    lifespan    = lifespan,
)

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origins_list,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ─────────────────────────────────────────────────
app.include_router(v1_router)

# ── Health root ──────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "status":    "running",
        "docs":      "/docs",
        "version":   "1.0.0",
        "providers": ["nptel", "codetantra", "coursera", "udemy"],
    }

# ── Dev runner ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host      = settings.HOST,
        port      = settings.PORT,
        reload    = False,
        log_level = settings.LOG_LEVEL,
    )
