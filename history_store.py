import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests

from web_search.config.settings import ROOT, connect, setting

HISTORY_DB = Path(os.getenv("HISTORY_DB", ROOT / ".research_agent" / "history.sqlite3"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL,
    provider TEXT NOT NULL,
    depth TEXT NOT NULL,
    digest TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    selected_provider TEXT,
    created_at TEXT NOT NULL
)
"""
INDEX = "CREATE INDEX IF NOT EXISTS idx_history_client ON research_history (client_id, created_at DESC, id DESC)"

_ready = False
_lock = threading.Lock()


def _turso():
    """Turso (hosted SQLite) is used when both variables are set, so history survives free-host restarts."""
    url, token = setting("TURSO_DATABASE_URL"), setting("TURSO_AUTH_TOKEN")
    if not (url and token):
        return None
    return url.replace("libsql://", "https://", 1).rstrip("/"), token


def _arg(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    return {"type": "text", "value": str(value)}


def _cell(cell):
    if cell["type"] == "null":
        return None
    if cell["type"] == "integer":
        return int(cell["value"])
    return cell["value"]


def _run_turso(target, sql, params):
    base, token = target
    body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [_arg(p) for p in params]}}, {"type": "close"}]}
    response = requests.post(f"{base}/v2/pipeline", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    response.raise_for_status()
    first = response.json()["results"][0]
    if first["type"] == "error":
        raise OSError(f"History database error: {first['error']['message']}")
    result = first["response"]["result"]
    rows = [[_cell(cell) for cell in row] for row in result["rows"]]
    last_id = result.get("last_insert_rowid")
    return rows, result.get("affected_row_count", 0), int(last_id) if last_id is not None else None


def _run_sqlite(sql, params):
    with connect(HISTORY_DB) as connection:
        cursor = connection.execute(sql, params)
        return cursor.fetchall(), cursor.rowcount, cursor.lastrowid


def _execute(sql, params=()):
    """Returns (rows, affected_rows, last_insert_id) from Turso or the local SQLite file."""
    global _ready
    target = _turso()
    run = (lambda s, p: _run_turso(target, s, p)) if target else _run_sqlite
    if not _ready:
        with _lock:
            if not _ready:
                run(SCHEMA, ())
                if not target:
                    _add_client_column_if_missing()
                run(INDEX, ())
                _ready = True
    try:
        return run(sql, tuple(params))
    except requests.RequestException as error:
        raise OSError(f"History database unreachable: {error}") from error


def _add_client_column_if_missing():
    columns = [row[1] for row in _run_sqlite("PRAGMA table_info(research_history)", ())[0]]
    if "client_id" not in columns:
        _run_sqlite("ALTER TABLE research_history ADD COLUMN client_id TEXT NOT NULL DEFAULT ''", ())


def save_entry(client_id, query, provider, depth, digest, sources, selected_provider):
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _, _, entry_id = _execute(
        "INSERT INTO research_history (client_id, query, provider, depth, digest, sources_json, source_count, selected_provider, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (client_id, query, provider, depth, digest, json.dumps(sources, ensure_ascii=False), len(sources), selected_provider, created_at),
    )
    return entry_id, created_at


def list_entries(client_id, limit=50, offset=0):
    """Lightweight rows only; the digest and sources are loaded on demand by get_entry."""
    rows, _, _ = _execute(
        "SELECT id, query, provider, depth, source_count, selected_provider, created_at "
        "FROM research_history WHERE client_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (client_id, limit, offset),
    )
    keys = ("id", "query", "provider", "depth", "source_count", "selected_provider", "created_at")
    return [dict(zip(keys, row)) for row in rows]


def get_entry(client_id, entry_id):
    rows, _, _ = _execute(
        "SELECT id, query, provider, depth, digest, sources_json, selected_provider, created_at "
        "FROM research_history WHERE id = ? AND client_id = ?",
        (entry_id, client_id),
    )
    if not rows:
        return None
    keys = ("id", "query", "provider", "depth", "digest", "sources_json", "selected_provider", "created_at")
    entry = dict(zip(keys, rows[0]))
    entry["sources"] = json.loads(entry.pop("sources_json"))
    return entry


def delete_entry(client_id, entry_id):
    _, affected, _ = _execute("DELETE FROM research_history WHERE id = ? AND client_id = ?", (entry_id, client_id))
    return affected > 0
