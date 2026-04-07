"""API entry point for the quant platform."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routes import assistant, brief_analysis, briefs, dashboard, drafts, health, preflight, projects, tables
from packages.shared.optimistic_lock import ConflictError

app = FastAPI(
    title="Quant Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.exception_handler(ConflictError)
async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Return HTTP 409 with merge/retry guidance on optimistic locking conflicts."""
    return JSONResponse(status_code=409, content=exc.to_response())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8510"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(projects.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(briefs.router, prefix="/api/v1")
app.include_router(brief_analysis.router, prefix="/api/v1")
app.include_router(preflight.router, prefix="/api/v1")
app.include_router(drafts.router, prefix="/api/v1")
app.include_router(tables.router, prefix="/api/v1")
