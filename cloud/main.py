"""
Enact Cloud — FastAPI backend.

Run locally:
    CLOUD_SECRET=changeme ENACT_EMAIL_DRY_RUN=1 uvicorn cloud.main:app --reload

Endpoints:
    POST   /receipts
    GET    /receipts/{run_id}
    POST   /hitl/request
    GET    /hitl/{hitl_id}
    GET    /hitl/{hitl_id}/approve?t=TOKEN
    POST   /hitl/{hitl_id}/approve?t=TOKEN
    GET    /hitl/{hitl_id}/deny?t=TOKEN
    POST   /hitl/{hitl_id}/deny?t=TOKEN
    GET    /badge/{team_id}/{workflow}.svg
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from cloud.db import init_db
from cloud.routes.receipts import router as receipts_router
from cloud.routes.hitl import router as hitl_router
from cloud.routes.badge import router as badge_router


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


app.include_router(receipts_router)
app.include_router(hitl_router)
app.include_router(badge_router)


@app.get("/health")
def health():
    return {"status": "ok"}
