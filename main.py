import os
from typing import Dict, Any, List, Optional

from fastapi import FastAPI
from fastmcp import FastMCP
from supabase import create_client, Client


# ---------- Supabase ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

sb: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "crochet"
COL_TITLE = "title"
COL_STATUS = "status"


def _db() -> Client:
    if sb is None:
        raise RuntimeError("Supabase not configured")
    return sb


def upsert_item(title: str, status: str) -> Dict[str, Any]:
    res = _db().table(TABLE).upsert(
        {COL_TITLE: title, COL_STATUS: status},
        on_conflict=COL_TITLE
    ).execute()
    return (res.data or [{}])[0]


def set_status(title: str, status: str) -> Dict[str, Any]:
    res = _db().table(TABLE).update(
        {COL_STATUS: status}
    ).eq(COL_TITLE, title).execute()
    return (res.data or [{}])[0]


def list_items() -> List[Dict[str, Any]]:
    res = _db().table(TABLE).select("title,status,notes").execute()
    return res.data or []


# ---------- MCP ----------
mcp = FastMCP("Lilazul MCP")

@mcp.tool
def ping() -> dict:
    return {"ok": True, "pong": "💜"}


@mcp.tool
def crochet_add(item: str, status: str = "wip") -> dict:
    row = upsert_item(item, status)
    return {
        "ok": True,
        "title": row.get(COL_TITLE, item),
        "status": row.get(COL_STATUS, status),
    }


@mcp.tool
def crochet_mark_done(item: str) -> dict:
    row = set_status(item, "done")
    return {
        "ok": True,
        "title": row.get(COL_TITLE, item),
        "status": row.get(COL_STATUS, "done"),
    }


@mcp.tool
def crochet_list() -> dict:
    return {"ok": True, "items": list_items()}


# ---------- FastAPI ----------
mcp_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_app.lifespan)

@app.get("/")
def root():
    return {"ok": True, "msg": "Lilazul API + MCP 💜"}

# ESTE endpoint lo usa tu UI
@app.post("/crochet")
def crochet_post(payload: Dict[str, Any]):
    title = payload.get("title")
    status = payload.get("status")

    if not title or not status:
        return {"ok": False, "error": "Missing title or status"}

    upsert_item(str(title), str(status))
    return {"ok": True}

@app.get("/crochet")
def crochet_get():
    return {"ok": True, "items": list_items()}

app.mount("/mcp", mcp_app)








