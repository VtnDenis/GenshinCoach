"""GenshinCoach store : SQLite local si TURSO_* absents, sinon Turso via Hrana HTTP."""
import json
import os
import sqlite3
import threading
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB = os.path.join(HERE, "conversations.db")
_lock = threading.Lock()


def _turso_cfg():
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    tok = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not url or not tok:
        return None
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    return url.rstrip("/") + "/v2/pipeline", tok


def _enc(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def _dec(c):
    t = c.get("type")
    v = c.get("value")
    if t == "null":
        return None
    if t == "integer":
        return int(v)
    if t == "float":
        return float(v)
    return v


def _turso(sql, args=()):
    endpoint, tok = _turso_cfg()
    body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [_enc(a) for a in args]}},
                         {"type": "close"}]}
    req = urllib.request.Request(
        endpoint, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        out = json.load(resp)
    entry = out["results"][0]
    if entry.get("type") == "error":
        raise RuntimeError(f"Turso error: {entry.get('error')}")
    result = entry["response"]["result"]
    cols = [c["name"] for c in result.get("cols", [])]
    return [dict(zip(cols, [_dec(c) for c in row])) for row in result.get("rows", [])]


def _local(sql, args=(), fetch=None):
    with _lock:
        con = sqlite3.connect(LOCAL_DB, timeout=10)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            cur = con.execute(sql, args)
            rows = None
            if fetch == "all":
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            elif fetch == "one":
                r = cur.fetchone()
                if r is not None and cur.description:
                    rows = dict(zip([d[0] for d in cur.description], r))
            con.commit()
            return rows
        finally:
            con.close()


def _q(sql, args=(), fetch=None):
    if _turso_cfg():
        return _turso(sql, args) if fetch else (_turso(sql, args) or None)
    return _local(sql, args, fetch)


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS genshin_sessions(
      id TEXT PRIMARY KEY, uid TEXT, title TEXT, created_at REAL, updated_at REAL)""",
    """CREATE TABLE IF NOT EXISTS genshin_messages(
      id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, created_at REAL)""",
]


def init_db():
    for sql in SCHEMA:
        _q(sql)


def new_session(uid, title=""):
    sid = uuid.uuid4().hex[:12]
    now = time.time()
    _q("INSERT INTO genshin_sessions(id,uid,title,created_at,updated_at) VALUES(?,?,?,?,?)",
       (sid, str(uid or ""), title[:80], now, now))
    return sid


def ensure_session(sid, uid):
    if not sid:
        return new_session(uid)
    rows = _q("SELECT id FROM genshin_sessions WHERE id=?", (sid,), fetch="all")
    if rows:
        return sid
    now = time.time()
    _q("INSERT INTO genshin_sessions(id,uid,title,created_at,updated_at) VALUES(?,?,?,?,?)",
       (sid, str(uid or ""), "", now, now))
    return sid


def list_sessions(limit=20):
    rows = _q("SELECT id,uid,title,created_at,updated_at FROM genshin_sessions "
              "ORDER BY updated_at DESC LIMIT ?", (max(1, min(50, limit)),), fetch="all")
    return rows or []


def get_messages(sid):
    rows = _q("SELECT role,content,created_at FROM genshin_messages WHERE session_id=? "
              "ORDER BY created_at ASC LIMIT 200", (sid,), fetch="all")
    return rows or []


def add_message(sid, role, content):
    _q("INSERT INTO genshin_messages(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)",
       (uuid.uuid4().hex, sid, role, content, time.time()))
    _q("UPDATE genshin_sessions SET updated_at=? WHERE id=?", (time.time(), sid))


def del_session(sid):
    _q("DELETE FROM genshin_messages WHERE session_id=?", (sid,))
    _q("DELETE FROM genshin_sessions WHERE id=?", (sid,))
