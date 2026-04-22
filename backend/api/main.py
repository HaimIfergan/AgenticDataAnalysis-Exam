import time
import uuid
import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# --- Configuration du Logging Structuré ---
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Agentic Data Analysis API",
    description="Backend de production pour l'analyse de données agentique",
    version="1.0.0"
)

# --- Middleware CORS ---
# Autorise uniquement l'origine du frontend en production (ici configuré largement pour le test)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production (ex: ["http://localhost:8501"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware Request ID & Logging ---
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next: Callable):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    process_time = time.perf_counter() - start_time
    
    response.headers["X-Request-ID"] = request_id
    
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration=f"{process_time:.4f}s"
    )
    return response

# --- Gestionnaire d'Exceptions Global ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("global_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Une erreur interne est survenue. Veuillez contacter le support.", "request_id": structlog.contextvars.get_contextvars().get("request_id")},
    )

# --- Métriques Prometheus ---
REQUEST_COUNT = Counter("api_requests_total", "Total des requêtes API", ["method", "endpoint", "http_status"])
REQUEST_LATENCY = Histogram("api_request_duration_seconds", "Latence des requêtes", ["endpoint"])

@app.get("/metrics")
def metrics():
    """Endpoint pour Prometheus afin de scraper les métriques."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# --- Endpoints Standard ---
@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé pour le monitoring."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API d'Agentic Data Analysis"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
