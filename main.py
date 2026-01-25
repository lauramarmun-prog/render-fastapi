from typing import Dict

from fastapi import FastAPI
from fastmcp import FastMCP

mcp = FastMCP("Lilazul MCP")

@mcp.tool
def ping() -> dict:
    """Simple health check tool to verify MCP calls work."""
    return {"ok": True, "pong": "💜"}

crochet_status: Dict[str, str] = {}

@mcp.tool
def crochet_mark_done(item: str) -> dict:
    """Mark a crochet item as finished."""
    crochet_status[item] = "done"
    return {"ok": True, "item": item, "status": "done"}

@mcp.tool
def crochet_list() -> dict:
    """List all crochet items and their status."""
    return {"ok": True, "items": crochet_status}


mcp_app = mcp.http_app(path="/")  # lo montamos en /mcp

app = FastAPI(lifespan=mcp_app.lifespan)

@app.get("/")
def root():
    return {"ok": True, "msg": "FastAPI alive + MCP mounted at /mcp 💜"}

app.mount("/mcp", mcp_app)





