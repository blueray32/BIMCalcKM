"""Enhanced FastAPI web UI for BIMCalc - Full-featured management interface."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from prometheus_fastapi_instrumentator import Instrumentator

from bimcalc.config import get_config
from bimcalc.core.logging import configure_logging
from bimcalc.intelligence.routes import router as intelligence_router

# Import modular routers
from bimcalc.web.routes import (
    auth,
    compliance,
    dashboard,
    ingestion,
    matching,
    review,
    items,
    mappings,
    reports,
    audit,
    pipeline,
    prices,
    projects,
    scenarios,
    crail4,
    revisions,
    integrations,
    documents,
    classifications,
    analytics,
    risk_dashboard,
)

# Initialize structured logging
configure_logging()
logger = structlog.get_logger()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(
    title="BIMCalc Management Console",
    description="Web interface for managing BIMCalc pricing data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Request Logging Middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        logger.info("request_started", 
            method=request.method, 
            path=request.url.path,
            client_ip=request.client.host
        )
        
        try:
            response = await call_next(request)
            
            logger.info("request_completed",
                status_code=response.status_code,
            )
            return response
            
        except Exception as exc:
            logger.error("request_failed", error=str(exc))
            raise

app.add_middleware(RequestLoggingMiddleware)

# Prometheus Metrics
Instrumentator().instrument(app).expose(app)

# Mount static files if directory exists
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions, specifically for redirects."""
    if exc.status_code in [301, 302, 303, 307, 308] and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# Include Routers
app.include_router(auth.router)
app.include_router(compliance.router)
app.include_router(dashboard.router)
app.include_router(ingestion.router)
app.include_router(matching.router)
app.include_router(review.router)
app.include_router(items.router)
app.include_router(mappings.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(pipeline.router)
app.include_router(prices.router)
app.include_router(projects.router)
app.include_router(scenarios.router)
app.include_router(crail4.router)
app.include_router(revisions.router)
app.include_router(integrations.router)
app.include_router(documents.router)
app.include_router(classifications.router)
app.include_router(analytics.router)
app.include_router(risk_dashboard.router)

# Intelligence Features (Conditional)
config = get_config()
if config.enable_rag or config.enable_risk_scoring:
    app.include_router(intelligence_router)
