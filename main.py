import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastmcp import FastMCP
from supabase import create_client, Client


# ==================================================
# CONFIG
# ==================================================
LILAZUL_API_BASE = os.getenv("LILAZUL_API_BASE", "https://lilazul-api.onrender.com")

TZ = ZoneInfo("Europe/Amsterdam")

def now_iso() -> str:
    return datetime.now(TZ).isoformat()


# ==================================================
# SUPABASE
# ==================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

sb: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def _db() -> Client:
    if sb is None:
        raise RuntimeError("Supabase not configured (missing SUPABASE_URL / SUPABASE_*_KEY)")
    return sb


# ==================================================
# CROCHET TABLE (Supabase)
# ==================================================
TABLE = "crochet"
COL_TITLE = "title"
COL_STATUS = "status"


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
    now = datetime.now(TZ)
    return {
        "current_time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"),
        "timezone": "Europe/Amsterdam",
        "iso": now.isoformat(),
    }


# ==================================================
# MOODS TABLE (Supabase)
# ==================================================
MOOD_TABLE = "mood"
MOOD_COL_OWNER = "owner"
MOOD_COL_MOOD = "mood"
MOOD_COL_UPDATED = "updated_at"


def _get_mood(owner: str) -> Dict[str, Any]:
    r = (
        _db()
        .table(MOOD_TABLE)
        .select(f"{MOOD_COL_OWNER},{MOOD_COL_MOOD},{MOOD_COL_UPDATED}")
        .eq(MOOD_COL_OWNER, owner)
        .maybe_single()
        .execute()
    )
    data = r.data or {}
    return {
        "owner": owner,
        "mood": data.get(MOOD_COL_MOOD, "") if isinstance(data, dict) else "",
        "updated_at": data.get(MOOD_COL_UPDATED, None) if isinstance(data, dict) else None,
    }


def _set_mood(owner: str, mood: str) -> Dict[str, Any]:
    payload = {
        MOOD_COL_OWNER: owner,
        MOOD_COL_MOOD: mood,
        MOOD_COL_UPDATED: now_iso(),
    }
    _db().table(MOOD_TABLE).upsert(payload).execute()
    return {"ok": True, "owner": owner, "mood": mood, "updated_at": payload[MOOD_COL_UPDATED]}


# ==================================================
# MCP TOOLS
# ==================================================
mcp = FastMCP("Lilazul MCP")

@mcp.tool
def get_time() -> dict:
    return get_time_context()

@mcp.tool
def ping() -> dict:
    return {"ok": True, "pong": "💜"}


# ---- Crochet tools ----
@mcp.tool
def crochet_add(item: str, status: str = "wip") -> dict:
    row = upsert_item(item, status)
    return {"ok": True, "id": row.get("id"), "title": row.get(COL_TITLE, item), "status": row.get(COL_STATUS, status)}

@mcp.tool
def crochet_mark_done(item: str) -> dict:
    row = set_status(item, "done")
    return {"ok": True, "id": row.get("id"), "title": row.get(COL_TITLE, item), "status": row.get(COL_STATUS, "done")}

@mcp.tool
def crochet_list() -> dict:
    return {"ok": True, "items": list_items()}

@mcp.tool
def crochet_toggle(id: str) -> dict:
    """Toggle usando el endpoint del backend principal."""
    url = f"{LILAZUL_API_BASE}/crochet/{id}/toggle"
    r = httpx.patch(url, timeout=10.0)
    r.raise_for_status()
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


# ---- Books tools ----
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
    payload = {"id": book_id or str(uuid4()), "title": title, "date": date}
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


# ---- Cakes tools ----
@mcp.tool
def cake_get(month: str | None = None) -> dict:
    url = f"{LILAZUL_API_BASE}/cake"
    if month:
        url += f"?month={month}"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "data": r.json()}

@mcp.tool
def cake_set(
    month: str,
    name: str = "",
    note: str = "",
    photo_url: str = "",
    recipe: str = ""
) -> dict:
    payload = {
        "month": month,
        "name": name,
        "note": note,
        "photo_url": photo_url,
        "recipe": recipe
    }
    url = f"{LILAZUL_API_BASE}/cake"
    r = httpx.put(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "data": r.json()}


@mcp.tool
def cake_delete(cake_id: str) -> dict:
    url = f"{LILAZUL_API_BASE}/cakes/{cake_id}"
    r = httpx.delete(url, timeout=10.0)
    r.raise_for_status()
    return {"ok": True, "id": cake_id}


# ---- Mood tools (lo que querías 💛) ----
@mcp.tool
def mood_get_lau() -> Dict[str, Any]:
    """Lee el mood actual de Lau desde Supabase."""
    return {"ok": True, **_get_mood("lau")}

@mcp.tool
def mood_set_geppie(mood: str) -> Dict[str, Any]:
    """Actualiza el mood de Geppie (solo Geppie escribe)."""
    return _set_mood("geppie", mood)


# ==================================================
# FASTAPI + MCP MOUNT
# ==================================================
mcp_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_app.lifespan)

@app.get("/")
def root():
    return {"ok": True, "msg": "Lilazul API + MCP 💜"}

# Endpoints crochet para la UI
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

# MCP mount
app.mount("/mcp", mcp_app)












