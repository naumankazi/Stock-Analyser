"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router

# Resolve paths relative to this file so the server works from any working directory
_BASE_DIR = Path(__file__).resolve().parent          # .../app/
_STATIC_DIR = _BASE_DIR / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

# Suppress noisy yfinance logs
logging.getLogger("yfinance").setLevel(logging.WARNING)
logging.getLogger("peewee").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Working directory : %s", os.getcwd())
    logger.info("Base directory    : %s", _BASE_DIR)
    logger.info("Static directory  : %s (exists=%s)", _STATIC_DIR, _STATIC_DIR.is_dir())
    if _STATIC_DIR.is_dir():
        files = list(_STATIC_DIR.iterdir())[:10]
        logger.info("Static files      : %s", [f.name for f in files])
    logger.info("Index HTML        : %s (exists=%s)", _INDEX_HTML, _INDEX_HTML.is_file())
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="Stock Technical Analysis Report Generator",
    description="Professional-grade technical analysis report cards for any stock.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (allow all for dev; restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router)

# Static frontend files — use absolute path so it works regardless of cwd
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the main SPA."""
    try:
        return FileResponse(
            str(_INDEX_HTML),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.exception("[root] Failed to serve index.html: %s", e)
        raise
