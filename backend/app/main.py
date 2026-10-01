"""EnviroPulse API — FastAPI application entry point.  Run: uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (routes_alerts, routes_analytics, routes_demo, routes_feedback, routes_health,
                     routes_source_health, routes_zones)
from app.core.config import get_settings
from app.core.logging import configure_logging, log
from app.workers import runner

logger = logging.getLogger("enviropulse.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    if s.enable_scheduler:
        runner.start()
    yield
    runner.stop()


app = FastAPI(
    title="EnviroPulse API",
    version="1.0.0",
    description=("Real-time air & water quality intelligence for industrial zones (PS 13 prototype). "
                 "Collect → Unify → Detect → Explain → Predict → Alert. Attribution results are estimates based "
                 "on association, never proof of causation. Simulated sources are labelled SIMULATED DEMO STREAM."),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log(logger, logging.ERROR, "unhandled error", path=request.url.path, error=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal error. The failure has been logged."})


for r in (routes_health, routes_source_health, routes_zones, routes_analytics, routes_alerts, routes_feedback,
          routes_demo):
    app.include_router(r.router)
