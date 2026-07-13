import os
import time
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.sse import SseServerTransport
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from .database import engine
from .models import Campaign, Job, RawCompanyRecord, EnrichedLead
from .mcp_server import server as mcp_server_instance
from .websocket_manager import ws_manager
from .proxy_rotator import ProxyRotator
from .rate_limiter import DomainRateLimiter
from .metrics import metrics_endpoint
from .logger import get_logger
from .auth import verify_token
from fastapi.responses import JSONResponse
from .routers import auth as auth_router
from .routers import jobs as jobs_router
from .routers import leads as leads_router
from .routers import companies as companies_router
from .routers import dashboard as dashboard_router
from .routers import misc as misc_router

log = get_logger("api")
request_log = get_logger("http")

app = FastAPI(title="Lead Generation Pipeline API", version="4.0.0")
rate_limiter = DomainRateLimiter()
proxy_rotator = ProxyRotator.from_env()

MCP_API_KEY = os.environ.get("MCP_API_KEY", "leadengine-secret-key")
sse = SseServerTransport("/messages")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    request_log.info("%s %s | status=%d duration=%.3fs | client=%s",
                     request.method, request.url.path, response.status_code, elapsed,
                     request.client.host if request.client else "unknown",
                     extra={"extra_fields": {
                         "method": request.method, "path": request.url.path,
                         "status": response.status_code, "duration_ms": round(elapsed * 1000, 2),
                         "client_ip": request.client.host if request.client else None,
                     }})
    return response


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if request.url.path in ["/sse", "/messages"]:
        if request.method == "OPTIONS":
            return await call_next(request)
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {MCP_API_KEY}":
            return Response(content="Unauthorized. Missing or invalid Authorization Bearer token.", status_code=401)
    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception | path=%s error=%s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": request.url.path},
    )


@app.on_event("startup")
async def startup():
    import redis.asyncio as aioredis
    rr = aioredis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    try:
        info = await rr.info()
        queue_len = info.get("db0", {}).get("keys", 0) if isinstance(info, dict) else 0
        from .metrics import scrape_rate
        scrape_rate.set(queue_len)
    except Exception:
        pass
    await rr.close()


@app.get("/metrics")
def metrics():
    return metrics_endpoint()


@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server_instance.run(read_stream, write_stream, mcp_server_instance.create_initialization_options())


@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


@app.websocket("/api/v1/ws/jobs/{job_id}")
async def websocket_job_events(websocket: WebSocket, job_id: int):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    await ws_manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(job_id, websocket)


app.include_router(auth_router.router)
app.include_router(jobs_router.router)
app.include_router(leads_router.router)
app.include_router(companies_router.router)
app.include_router(dashboard_router.router)
app.include_router(misc_router.router)


frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def root_fallback():
        return {"message": "Lead Generation Pipeline API is running. Frontend dist folder not found."}


if __name__ == "__main__":
    import uvicorn
    print("Starting Lead Generation Studio API v4.0 on http://localhost:8000")
    uvicorn.run("lead_generation_app.backend.app:app", host="0.0.0.0", port=8000, reload=True)
