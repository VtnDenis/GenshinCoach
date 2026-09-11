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
        rows = _turso(sql, args) or []
        if fetch == "one":
            return rows[0] if rows else None
        if fetch == "all":
            return rows
        return rows or None
    return _local(sql, args, fetch)


def _q_resilient(sql, args=(), fetch=None):
    """_q + auto-init si les tables manquent (ex. nouvelle BDD Turso vide), 1 retry."""
    try:
        return _q(sql, args, fetch)
    except Exception as ex:
        if "no such table" not in str(ex).lower():
            raise
        init_db()
        return _q(sql, args, fetch)


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS genshin_sessions(
      id TEXT PRIMARY KEY, uid TEXT, title TEXT, created_at REAL, updated_at REAL)""",
    """CREATE TABLE IF NOT EXISTS genshin_messages(
      id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, created_at REAL)""",
    """CREATE TABLE IF NOT EXISTS genshin_thinking(
      message_id TEXT PRIMARY KEY, thinking TEXT, secs REAL,
      answer_secs REAL, out_tokens INTEGER)""",
]


def _columns(table):
    try:
        rows = _q(f"PRAGMA table_info({table})", fetch="all")
        return {r["name"] for r in rows or []}
    except Exception:
        return set()


def init_db():
    for sql in SCHEMA:
        _q(sql)
    # migration BDD existantes (créées avant les colonnes stats)
    cols = _columns("genshin_thinking")
    for col, typ in (("answer_secs", "REAL"), ("out_tokens", "INTEGER")):
        if col not in cols:
            try:
                _q(f"ALTER TABLE genshin_thinking ADD COLUMN {col} {typ}")
            except Exception:
                pass


def new_session(uid, title=""):
    sid = uuid.uuid4().hex[:12]
    now = time.time()
    _q_resilient("INSERT INTO genshin_sessions(id,uid,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                 (sid, str(uid or ""), title[:80], now, now))
    return sid


def ensure_session(sid, uid):
    if not sid:
        return new_session(uid)
    rows = _q_resilient("SELECT id FROM genshin_sessions WHERE id=?", (sid,), fetch="all")
    if rows:
        return sid
    now = time.time()
    _q_resilient("INSERT INTO genshin_sessions(id,uid,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                 (sid, str(uid or ""), "", now, now))
    return sid


def get_session(sid):
    rows = _q_resilient("SELECT id,uid,title,created_at,updated_at FROM genshin_sessions WHERE id=?",
                        (sid,), fetch="all")
    return rows[0] if rows else None


def set_title(sid, title):
    t = (title or "").strip().replace("\n", " ")[:60]
    if not t:
        return
    _q_resilient("UPDATE genshin_sessions SET title=?,updated_at=? WHERE id=?",
                 (t, time.time(), sid))


def list_sessions(limit=20):
    rows = _q_resilient("SELECT id,uid,title,created_at,updated_at FROM genshin_sessions "
                        "ORDER BY updated_at DESC LIMIT ?", (max(1, min(50, limit)),), fetch="all")
    out = []
    for r in rows or []:
        n = _q_resilient("SELECT COUNT(*) AS n FROM genshin_messages WHERE session_id=?",
                         (r["id"],), fetch="one")
        r["n"] = (n or {}).get("n", 0)
        out.append(r)
    return out


def get_messages(sid):
    rows = _q_resilient(
        "SELECT m.role,m.content,m.created_at,t.thinking,t.secs,t.answer_secs,t.out_tokens "
        "FROM genshin_messages m "
        "LEFT JOIN genshin_thinking t ON t.message_id=m.id WHERE m.session_id=? "
        "ORDER BY m.created_at ASC LIMIT 200", (sid,), fetch="all")
    return rows or []


def add_message(sid, role, content):
    mid = uuid.uuid4().hex
    _q_resilient("INSERT INTO genshin_messages(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)",
                 (mid, sid, role, content, time.time()))
    _q_resilient("UPDATE genshin_sessions SET updated_at=? WHERE id=?", (time.time(), sid))
    return mid


def save_thinking(mid, thinking, secs=None, answer_secs=None, out_tokens=None):
    if not thinking and answer_secs is None and out_tokens is None:
        return
    try:
        _q_resilient("INSERT OR REPLACE INTO genshin_thinking"
                     "(message_id,thinking,secs,answer_secs,out_tokens) VALUES(?,?,?,?,?)",
                     (mid, (thinking or "")[:4000], secs, answer_secs, out_tokens))
    except Exception:
        pass


def del_session(sid):
    rows = _q_resilient("SELECT id FROM genshin_messages WHERE session_id=?", (sid,), fetch="all")
    for r in rows or []:
        try:
            _q_resilient("DELETE FROM genshin_thinking WHERE message_id=?", (r["id"],))
        except Exception:
            pass
    _q_resilient("DELETE FROM genshin_messages WHERE session_id=?", (sid,))
    _q_resilient("DELETE FROM genshin_sessions WHERE id=?", (sid,))
