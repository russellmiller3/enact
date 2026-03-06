"""
Enact Cloud — FastAPI backend.

Run locally:
    CLOUD_SECRET=changeme ENACT_EMAIL_DRY_RUN=1 uvicorn cloud.main:app --reload

Endpoints:
    POST   /receipts
    GET    /receipts/{run_id}
    GET    /receipts
    POST   /hitl/request
    GET    /hitl/{hitl_id}
    GET    /hitl/{hitl_id}/approve?t=TOKEN
    POST   /hitl/{hitl_id}/approve?t=TOKEN
    GET    /hitl/{hitl_id}/deny?t=TOKEN
    POST   /hitl/{hitl_id}/deny?t=TOKEN
    GET    /badge/{team_id}/{workflow}.svg

Auditor API (for SOC 2, SOX, EU AI Act compliance):
    GET    /auditor/receipts/{run_id}
    GET    /auditor/receipts
    GET    /auditor/stats
"""
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from cloud.db import init_db
from cloud.routes.receipts import router as receipts_router
from cloud.routes.hitl import router as hitl_router
from cloud.routes.badge import router as badge_router
from cloud.routes.auditor import router as auditor_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("CLOUD_SECRET"):
        raise RuntimeError(
            "CLOUD_SECRET env var is required. "
            "Set it with: export CLOUD_SECRET=$(openssl rand -hex 32)"
        )
    init_db()
    yield


app = FastAPI(title="Enact Cloud", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate limiting (stdlib, no extra deps) ────────────────────────────────────
# Sliding window per IP: 60 requests/minute for writes, 120/minute for reads.
# Keeps a dict of {ip: [timestamps]}. Entries older than the window are pruned.

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_WRITE_LIMIT = 60       # POST requests per minute
_READ_LIMIT = 120       # GET requests per minute
_WINDOW = 60.0          # seconds


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Skip rate limiting for health checks and static assets
    if request.url.path in ("/health", "/dashboard") or request.url.path.startswith("/static"):
        return await call_next(request)

    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[ip]

    # Prune expired entries
    bucket[:] = [t for t in bucket if now - t < _WINDOW]

    limit = _WRITE_LIMIT if request.method == "POST" else _READ_LIMIT
    if len(bucket) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again shortly."},
        )

    bucket.append(now)
    return await call_next(request)


app.include_router(receipts_router)
app.include_router(hitl_router)
app.include_router(badge_router)
app.include_router(auditor_router)

# Serve static dashboard files
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))
