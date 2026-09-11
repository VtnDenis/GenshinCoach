"""GenshinCoach API: ThreadingHTTPServer, stdlib only.
  python api/server.py -> http://127.0.0.1:8000 (local) ou $PORT (Render)
Routes: GET /api/health  GET /api/showcase?uid=  GET /api/news?q=&k=
  GET /api/sessions?n=  GET /api/sessions/<id>/messages  DELETE /api/sessions/<id>
  POST /api/chat {question,uid?,session_id?} -> {answer,model,session_id,detailed}
  POST /api/chat/stream {question,uid?,session_id?} -> SSE (delta/done/error)
Sert web/ statique (pas de build). FS Render éphémère -> état via Turso (cf. store).
"""
import json
import os
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import genshin
import store

PORT = int(os.environ.get("PORT", os.environ.get("GENSHIN_PORT", "8000")))
HOST = os.environ.get("GENSHIN_HOST", "0.0.0.0")
HERE = os.path.dirname(os.path.abspath(__file__))
WEB_BUILD = os.path.join(os.path.dirname(HERE), "web", "build")
WEB_DIR = WEB_BUILD if os.path.isdir(WEB_BUILD) else os.path.join(os.path.dirname(HERE), "web")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
        ".json": "application/json", ".ico": "image/x-icon", ".png": "image/png"}


def _json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _body(handler, limit=256 * 1024):
    try:
        n = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        n = 0
    if n <= 0 or n > limit:
        return {}
    try:
        return json.loads(handler.rfile.read(n).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _db_error(ex):
    """Message clair quand la BDD est injoignable (au lieu d'un 500 vide)."""
    s = str(ex)
    if "401" in s or "Unauthorized" in s or "InvalidToken" in s:
        return ("BDD inaccessible (token refusé) : le TURSO_AUTH_TOKEN ne correspond "
                "pas à cette BDD. Mets à jour TURSO_AUTH_TOKEN (local : .env, prod : dashboard Render).")
    if "404" in s or "not found" in s.lower():
        return "BDD introuvable : vérifie TURSO_DATABASE_URL."
    return s[:300]


def _toks(out, secs):
    try:
        return round(out / secs, 1) if out and secs else None
    except (TypeError, ZeroDivisionError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "GenshinCoach/1.0"

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ----- GET -----
    def do_GET(self):
        try:
            parts = urllib.parse.urlparse(self.path)
            path, qs = parts.path, urllib.parse.parse_qs(parts.query)
            if path == "/api/health":
                return _json(self, {"ok": True, "service": "genshincoach",
                                    "uid_default": genshin.DEFAULT_UID, "ts": time.time()})
            if path == "/api/showcase":
                uid = (qs.get("uid") or [genshin.DEFAULT_UID])[0]
                data = genshin.fetch_showcase(uid)
                a = genshin.audit_showcase(data)
                p = data.get("playerInfo", {})
                return _json(self, {"uid": str(uid),
                                    "player": {"nickname": p.get("nickname"), "level": p.get("level"),
                                               "worldLevel": p.get("worldLevel"),
                                               "achievements": p.get("finishAchievementNum")},
                                    "detailed": a["detailed"], "characters": a["characters"],
                                    "preview": a["preview"], "priorities": a["priorities"]})
            if path == "/api/news":
                q = (qs.get("q") or ["patch notes"])[0]
                k = int((qs.get("k") or ["5"])[0])
                r = genshin.tavily_search(f"Genshin Impact {q} Hoyolab", k=max(1, min(8, k)))
                return _json(self, r)
            if path == "/api/sessions":
                n = int((qs.get("n") or ["20"])[0])
                try:
                    return _json(self, {"sessions": store.list_sessions(n)})
                except Exception as ex:
                    traceback.print_exc()
                    return _json(self, {"error": _db_error(ex)}, 500)
            seg = path.strip("/").split("/")
            if len(seg) == 4 and seg[0] == "api" and seg[1] == "sessions" and seg[3] == "messages":
                try:
                    return _json(self, {"messages": store.get_messages(seg[2])})
                except Exception as ex:
                    traceback.print_exc()
                    return _json(self, {"error": _db_error(ex)}, 500)
            # statique
            return self._static(path)
        except Exception as ex:
            traceback.print_exc()
            return _json(self, {"error": str(ex)[:300]}, 500)

    # ----- POST -----
    def do_POST(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/chat":
                b = _body(self)
                q = (b.get("question") or "").strip()
                if not q:
                    return _json(self, {"error": "question vide"}, 400)
                uid = str(b.get("uid") or genshin.DEFAULT_UID)
                try:
                    sid = store.ensure_session(b.get("session_id") or "", uid)
                    sess = store.get_session(sid)
                    hist = [{"role": m["role"], "content": m["content"]}
                            for m in store.get_messages(sid)[-8:]]
                except Exception as ex:
                    traceback.print_exc()
                    return _json(self, {"error": _db_error(ex)}, 500)
                r = genshin.ask(q, uid=uid, history=hist, session_key=sid)
                st = r.get("stats") or {}
                try:
                    store.add_message(sid, "user", q)
                    amid = store.add_message(sid, "assistant", r["answer"])
                    store.save_thinking(amid, r.get("thinking") or "",
                                        None, st.get("llm_s"), st.get("out"))
                    if not (sess or {}).get("title"):
                        store.set_title(sid, q)
                except Exception as ex:
                    traceback.print_exc()
                    return _json(self, {"error": _db_error(ex)}, 500)
                try:
                    det = r.get("detailed")
                    if det is None:
                        try:
                            data = genshin.fetch_showcase(uid)
                            det = bool(data.get("avatarInfoList"))
                        except Exception:
                            det = False
                except Exception:
                    det = False
                return _json(self, {"answer": r["answer"], "model": r["model"],
                                    "thinking": r.get("thinking") or "",
                                    "steps": r.get("steps") or [],
                                    "stats": {"total_s": st.get("total_s"),
                                              "toks": _toks(st.get("out"), st.get("llm_s")),
                                              "out": st.get("out")},
                                    "session_id": sid, "detailed": det})
            if path == "/api/chat/stream":
                b = _body(self)
                q = (b.get("question") or "").strip()
                if not q:
                    return _json(self, {"error": "question vide"}, 400)
                uid = str(b.get("uid") or genshin.DEFAULT_UID)
                try:
                    sid = store.ensure_session(b.get("session_id") or "", uid)
                    sess = store.get_session(sid)
                    hist = [{"role": m["role"], "content": m["content"]}
                            for m in store.get_messages(sid)[-8:]]
                except Exception as ex:
                    traceback.print_exc()
                    return _json(self, {"error": _db_error(ex)}, 500)
                msgs = None
                model = genshin.E("OMNIROUTE_MODEL", "auto")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                def emit(obj):
                    self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False)
                                      + "\n\n").encode())
                    self.wfile.flush()

                try:
                    emit({"meta": {"session_id": sid}})
                except (BrokenPipeError, ConnectionResetError):
                    return
                # Boucle agent (logique RunCoach) APRÈS le premier event :
                # steps + thinking en live, seule la réponse finale est affichée.
                full, think_parts = [], []
                steps_all = []
                done_detailed = None
                done_model = None
                t_start = time.time()
                think_secs = None
                t_first_ans = None
                out_tokens = None
                try:
                    for ev in genshin.ask_stream(q, uid=uid, history=hist, session_key=sid):
                        et = ev.get("type")
                        if et == "thinking":
                            d = ev.get("delta") or ""
                            if d:
                                think_parts.append(d)
                                try:
                                    emit({"thinking": d})
                                except (BrokenPipeError, ConnectionResetError):
                                    break
                        elif et == "step_end":
                            st = {"tool": ev.get("tool"), "ms": ev.get("ms"),
                                  "result": (ev.get("result") or "")[:300],
                                  "error": ev.get("error") or ""}
                            steps_all.append(st)
                            try:
                                emit({"step": st})
                            except (BrokenPipeError, ConnectionResetError):
                                break
                        elif et == "token":
                            d = ev.get("delta") or ""
                            if think_secs is None:
                                think_secs = round(time.time() - t_start, 1)
                                t_first_ans = time.time()
                            full.append(d)
                            try:
                                emit({"delta": d})
                            except (BrokenPipeError, ConnectionResetError):
                                break
                        elif et == "done":
                            full = [ev.get("answer") or "".join(full)]
                            done_detailed = ev.get("detailed")
                            done_model = ev.get("model") or None
                            if ev.get("steps"):
                                steps_all = ev["steps"]
                            think_parts = [ev.get("thinking") or "".join(think_parts)]
                            break
                        elif et == "error":
                            raise RuntimeError(ev.get("error") or "erreur agent")
                        # step_start ignoré : step_end porte la trace complète
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as ex:
                    traceback.print_exc()
                    try:
                        emit({"error": str(ex)[:300]})
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                answer = "".join(full)
                if done_model:
                    model = done_model
                thinking = "".join(think_parts)
                t_end = time.time()
                if think_secs is None:
                    think_secs = round(t_end - t_start, 1)
                answer_secs = round(t_end - t_first_ans, 1) if t_first_ans else None
                total_s = round(t_end - t_start, 1)
                toks = _toks(out_tokens, answer_secs)
                try:
                    try:
                        det = done_detailed
                        if det is None:
                            data = genshin.fetch_showcase(uid)
                            det = bool(data.get("avatarInfoList"))
                    except Exception:
                        det = False
                    if answer:
                        store.add_message(sid, "user", q)
                        amid = store.add_message(sid, "assistant", answer)
                        store.save_thinking(amid, thinking, think_secs, answer_secs, out_tokens)
                        if not (sess or {}).get("title"):
                            store.set_title(sid, q)
                    emit({"done": {"session_id": sid, "model": model, "detailed": det,
                                   "thinking": thinking, "think_secs": think_secs,
                                   "steps": steps_all,
                                   "stats": {"total_s": total_s, "toks": toks,
                                             "out": out_tokens}}})
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as ex:
                    traceback.print_exc()
                    try:
                        emit({"error": _db_error(ex)})
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                return
            return _json(self, {"error": "not found"}, 404)
        except Exception as ex:
            traceback.print_exc()
            return _json(self, {"error": str(ex)[:300]}, 500)

    # ----- DELETE -----
    def do_DELETE(self):
        try:
            seg = urllib.parse.urlparse(self.path).path.strip("/").split("/")
            if len(seg) == 3 and seg[0] == "api" and seg[1] == "sessions":
                store.del_session(seg[2])
                return _json(self, {"ok": True})
            return _json(self, {"error": "not found"}, 404)
        except Exception as ex:
            return _json(self, {"error": str(ex)[:300]}, 500)

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        if ".." in rel or rel.startswith("/"):
            return _json(self, {"error": "not found"}, 404)
        fp = os.path.join(WEB_DIR, rel)
        if os.path.isdir(fp):
            fp = os.path.join(fp, "index.html")
        if not os.path.isfile(fp):
            fp = os.path.join(WEB_DIR, "index.html")
            if not os.path.isfile(fp):
                return _json(self, {"error": "not found"}, 404)
        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, "rb") as f:
                body = f.read()
        except OSError:
            return _json(self, {"error": "not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    try:
        store.init_db()
    except Exception as ex:
        # BDD injoignable (token périmé, URL fausse…) : on démarre quand même,
        # les endpoints renvoient un message clair au lieu d'un crash au boot.
        print(f"WARN init_db: {ex} (le serveur démarre, l'historique est dégradé)", flush=True)
    print(f"GenshinCoach on {HOST}:{PORT} (web={WEB_DIR})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
