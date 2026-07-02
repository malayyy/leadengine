from fastapi import FastAPI, Request, Response
from mcp.server.sse import SseServerTransport
import os
import uvicorn

# Import the existing tools from the stdio server definition
from .mcp_server import server

app = FastAPI(title="Lead Engine MCP Server (HTTP)")

API_KEY = os.environ.get("MCP_API_KEY", "leadengine-secret-key")

# We mount the SSE endpoint at /messages
# Note: SseServerTransport manages the routing for /sse (GET) and /messages (POST) natively 
# when instantiated this way and used with its ASGI wrappers.
# But since we are integrating with FastAPI, we can just map them manually.

sse = SseServerTransport("/messages")

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    # Skip auth for OPTIONS (CORS) or health checks if needed
    if request.method == "OPTIONS":
        return await call_next(request)
        
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return Response(content="Unauthorized. Missing or invalid Authorization Bearer token.", status_code=401)
        
    return await call_next(request)

@app.get("/sse")
async def handle_sse(request: Request):
    """
    Hermes connects here first using a GET request.
    It returns an EventSource stream.
    """
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    """
    Hermes POSTs tool execution requests here.
    """
    await sse.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
