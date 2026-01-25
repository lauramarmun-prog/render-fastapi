from fastapi import FastAPI
from fastmcp import FastMCP

mcp = FastMCP("Lilazul MCP")

@mcp.tool
def ping() -> dict:
    """Simple health check tool to verify MCP calls work."""
    return {"ok": True, "pong": "💜"}

mcp_app = mcp.http_app(path="/")  # path="/" porque lo vamos a montar en /mcp

app = FastAPI(lifespan=mcp_app.lifespan)

@app.get("/")
def root():
    return {"ok": True, "msg": "FastAPI alive + MCP mounted at /mcp 💜"}

app.mount("/mcp", mcp_app)



