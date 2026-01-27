import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from uuid import uuid4
import httpx

import httpx
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
    res = _db().table(TABLE).select("id,title,status,notes").execute()
    return res.data or []

def get_time_context() -> Dict[str, Any]:
    tz = ZoneInfo("Europe/Amsterdam")
    now = datetime.now(tz)

    return {
        "current_time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"),
        "timezone": "Europe/Amsterdam",
        "iso": now.isoformat()
    }



# ---------- MCP ----------
mcp = FastMCP("Lilazul MCP")

# Si algún día cambias el backend de tu app, lo puedes apuntar aquí sin tocar código:
LILAZUL_API_BASE = os.getenv("LILAZUL_API_BASE", "https://lilazul-api.onrender.com")

@mcp.tool
def get_time() -> dict:
    return get_time_context()


@mcp.tool
def ping() -> dict:
    return {"ok": True, "pong": "💜"}


@mcp.tool
def crochet_add(item: str, status: str = "wip") -> dict:
    row = upsert_item(item, status)
    return {
        "ok": True,
        "id": row.get("id"),
        "title": row.get(COL_TITLE, item),
        "status": row.get(COL_STATUS, status),
    }


@mcp.tool
def crochet_mark_done(item: str) -> dict:
    row = set_status(item, "done")
    return {
        "ok": True,
        "id": row.get("id"),
        "title": row.get(COL_TITLE, item),
        "status": row.get(COL_STATUS, "done"),
    }


@mcp.tool
def crochet_list() -> dict:
    return {"ok": True, "items": list_items()}


@mcp.tool
def crochet_toggle(id: str) -> dict:
    """
    Toggle status using the SAME endpoint your web app uses:
    PATCH /crochet/{id}/toggle on lilazul-api.onrender.com
    """
    url = f"{LILAZUL_API_BASE}/crochet/{id}/toggle"
    r = httpx.patch(url, timeout=10.0)
    r.raise_for_status()
    # devolvemos respuesta si viene JSON
    try:
        data = r.json()
    except Exception:
        data = None
    return {"ok": True, "id": id, "api_status": r.status_code, "response": data}
    
@mcp.tool
def crochet_delete(item_id: str) -> dict:
    url = f"{LILAZUL_API_BASE}/crochet/{item_id}"
    r = httpx.delete(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "id": item_id}

@mcp.tool
def book_get_current() -> dict:
    url = f"{LILAZUL_API_BASE}/current-book"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "book": r.json()}
@mcp.tool
def book_set_current(title: str, author: str | None = None) -> dict:
    payload = {"title": title, "author": author}
    url = f"{LILAZUL_API_BASE}/current-book"
    r = httpx.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "book": r.json()}
@mcp.tool
def book_list_finished() -> dict:
    url = f"{LILAZUL_API_BASE}/finished-books"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "books": r.json()}

@mcp.tool
def book_add_finished(title: str, date: str, book_id: str | None = None) -> dict:
    payload = {
        "id": book_id or str(uuid4()),
        "title": title,
        "date": date,  # formato recomendado: "2025-10-07"
    }
    url = f"{LILAZUL_API_BASE}/finished-books"
    r = httpx.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "book": r.json()}
    
@mcp.tool
def book_delete_finished(book_id: str) -> dict:
    url = f"{LILAZUL_API_BASE}/finished-books/{book_id}"
    r = httpx.delete(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "id": book_id}
@mcp.tool
def cake_get(month: str | None = None) -> dict:
    """
    Lee la tarta:
    - si pasas month="YYYY-MM" -> ese mes
    - si no pasas month -> la más reciente
    """
    url = f"{LILAZUL_API_BASE}/cake"
    if month:
        url += f"?month={month}"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "data": r.json()}


@mcp.tool
def cake_set(month: str, name: str = "", note: str = "", photo_url: str = "") -> dict:
    """
    Guarda/actualiza la tarta del mes (upsert por month).
    month debe ser "YYYY-MM" (ej: "2026-02").
    """
    payload = {
        "month": month,
        "name": name,
        "note": note,
        "photo_url": photo_url,
    }
    url = f"{LILAZUL_API_BASE}/cake"
    r = httpx.put(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "data": r.json()}



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








