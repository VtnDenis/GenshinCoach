"""GenshinCoach — logique métier : Enka + meta + LLM. Stdlib only."""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DOTENV = os.path.join(os.path.dirname(HERE), ".env")
CACHE_CHARS = os.path.join(HERE, ".cache_chars.json")
CACHE_JMP = os.path.join(HERE, ".cache_jmp.json")

DEFAULT_UID = os.environ.get("GENSHIN_DEFAULT_UID", "702342940")

_enka_cache = {}   # uid -> (ts, data)
_chars_cache = None  # avatarId -> meta
_ALIASES = {"ambor": "amber", "noel": "noelle", "linette": "lynette",
             "playerboy": "traveler-anemo", "playergirl": "traveler-anemo"}
_jmp_cache = None


def E(key, default=""):
    return os.environ.get(key, default)


def _load_dotenv():
    try:
        with open(DOTENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_dotenv()


def _http_json(url, method="GET", data=None, headers=None, timeout=20):
    body = json.dumps(data).encode() if data is not None else None
    h = {"User-Agent": "GenshinCoach/1.0", "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# ---------- Enka ----------

def fetch_showcase(uid):
    uid = str(uid or DEFAULT_UID)
    now = time.time()
    hit = _enka_cache.get(uid)
    if hit and now - hit[0] < 300:
        return hit[1]
    data = _http_json(f"https://enka.network/api/uid/{uid}", timeout=25)
    _enka_cache[uid] = (now, data)
    return data


# ---------- Meta statique (Enka docs + jmp.blue, gratuit, sans clé) ----------

def _load_chars():
    global _chars_cache
    if _chars_cache is not None:
        return _chars_cache
    try:
        with open(CACHE_CHARS, encoding="utf-8") as f:
            blob = json.load(f)
        if time.time() - blob.get("_ts", 0) < 30 * 86400:
            _chars_cache = blob["chars"]
            return _chars_cache
    except (OSError, ValueError, KeyError):
        pass
    raw = _http_json(
        "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/characters.json",
        timeout=30)
    out = {}
    for avid, c in raw.items():
        if not str(avid).isdigit():
            continue
        side = c.get("SideIconName", "")
        m = re.match(r"UI_AvatarIcon_Side_(.+)", side)
        jmp = _ALIASES.get((m.group(1) if m else "").lower(),
                          (m.group(1) if m else "").lower())
        out[str(avid)] = {
            "element": c.get("Element", "?"),
            "rarity": 5 if c.get("QualityType") == "QUALITY_ORANGE" else 4,
            "weapon": (c.get("WeaponType", "").replace("WEAPON_", "").replace("_", " ").title()),
            "jmp": jmp,
        }
    _chars_cache = out
    try:
        with open(CACHE_CHARS, "w", encoding="utf-8") as f:
            json.dump({"_ts": time.time(), "chars": out}, f)
    except OSError:
        pass
    return out


def char_meta(avatar_id):
    return _load_chars().get(str(avatar_id), {"element": "?", "rarity": 4, "weapon": "?", "jmp": ""})


def _load_jmp():
    global _jmp_cache
    if _jmp_cache is not None:
        return _jmp_cache
    try:
        with open(CACHE_JMP, encoding="utf-8") as f:
            blob = json.load(f)
        if time.time() - blob.get("_ts", 0) < 30 * 86400:
            _jmp_cache = blob["items"]
            return _jmp_cache
    except (OSError, ValueError, KeyError):
        pass
    _jmp_cache = {}
    try:
        with open(CACHE_JMP, "w", encoding="utf-8") as f:
            json.dump({"_ts": time.time(), "items": {}}, f)
    except OSError:
        pass
    return _jmp_cache


def jmp_detail(jmp_id):
    """Détail perso via genshin.jmp.blue (cache fichier)."""
    if not jmp_id:
        return {}
    cache = _load_jmp()
    if jmp_id in cache:
        return cache[jmp_id]
    try:
        d = _http_json(f"https://genshin.jmp.blue/characters/{jmp_id}", timeout=20)
    except Exception:
        return {}
    keep = {k: d.get(k) for k in ("name", "title", "vision", "weapon", "nation",
                                  "affiliation", "rarity", "constellation", "description")
            if d.get(k) is not None}
    cache[jmp_id] = keep
    try:
        with open(CACHE_JMP, "w", encoding="utf-8") as f:
            json.dump({"_ts": time.time(), "items": cache}, f)
    except OSError:
        pass
    return keep


# ---------- Audit déterministe ----------

def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def audit_avatar(av):
    """Analyse un avatar détaillé Enka -> dict + findings."""
    avid = str(av.get("avatarId", "?"))
    meta = char_meta(avid)
    name = (jmp_detail(meta["jmp"]).get("name") if meta["jmp"] else "") or f"Perso {avid}"
    level = int(av.get("propMap", {}).get("4001", {}).get("val", 0) or 0)
    cons = len(av.get("talentIdList") or [])
    skills = {str(k): int(v) for k, v in (av.get("skillLevelMap") or {}).items()}
    fp = av.get("fpt", av.get("fightPropMap", {}))
    crit_r = _num(fp.get("20")) * (100 if _num(fp.get("20")) < 1 else 1) if "20" in fp else None
    if crit_r is not None and crit_r > 100:
        crit_r = _num(fp.get("20"))
    crit_d = _num(fp.get("22")) * (100 if _num(fp.get("22")) < 1 else 1) if "22" in fp else None
    if crit_d is not None and crit_d > 500:
        crit_d = _num(fp.get("22"))
    er = _num(fp.get("23")) * (100 if _num(fp.get("23")) < 1 else 1) if "23" in fp else None
    if er is not None and er > 1000:
        er = _num(fp.get("23"))

    weapon, arts = None, []
    for eq in av.get("equipList") or []:
        flat = eq.get("flat") or {}
        if flat.get("itemType") == "ITEM_WEAPON" or "weapon" in eq:
            w = eq.get("weapon") or {}
            weapon = {"level": int(w.get("level", 0) or 0),
                      "rank": int(flat.get("rankLevel", 0) or 0),
                      "refine": len(w.get("affixMap") or {}),
                      "id": flat.get("nameTextMapHash", "?")}
        elif flat.get("itemType") == "ITEM_RELIQUARY" or "reliquary" in eq:
            r = eq.get("reliquary") or {}
            arts.append({"level": int(r.get("level", 0) or 0),
                         "rank": int(flat.get("rankLevel", 0) or 0),
                         "set": str(flat.get("setNameTextMapHash", "?"))})

    findings = []
    if level < 50:
        findings.append(f"Niveau {level} < 50 : à monter en priorité si c'est un main (cap AR30 = 60/70).")
    if weapon:
        if weapon["level"] < max(20, level - 10):
            findings.append(f"Arme niv. {weapon['level']} en retard sur perso {level} : zweiten prio après le niveau.")
        if weapon["rank"] <= 3:
            findings.append(f"Arme {weapon['rank']}★ : penser à la remplacer par une 4★ forgeable/gacha.")
    else:
        findings.append("Pas d'arme détectée.")
    if len(arts) < 4:
        findings.append(f"Seulement {len(arts)}/5 artefacts : compléter le set (même en 4★).")
    else:
        avg = sum(a["level"] for a in arts) / len(arts)
        if avg < 8:
            findings.append(f"Artefacts moy. +{avg:.0f} : les monter à +8/+12 rapporte plus que farmer du 5★ à AR30.")
        if any(a["rank"] <= 3 for a in arts):
            findings.append("Artefacts 3★ équipés : à remplacer par 4★ (coffres/boss).")
    if skills and max(skills.values()) < 4 and level >= 40:
        findings.append("Talents bas : monter le skill principal à 6 (livres + boss hebdo).")
    if crit_r is not None and crit_d is not None and (crit_r + 1) > 1:
        if crit_r < 50:
            findings.append(f"Taux crit {crit_r:.0f}% < 50% : viser 60%+ via casque Taux + sous-stats.")
        if crit_d < 100:
            findings.append(f"DGT crit {crit_d:.0f}% < 100% : ratio cible ~1:2 (ex 60/120).")
    if er is not None and er < 100:
        findings.append(f"Recharge {er:.0f}% : anormalement basse, vérifier sablier/arme ER pour les supports.")

    return {"id": avid, "name": name, "element": meta["element"], "rarity": meta["rarity"],
            "weapon_type": meta["weapon"], "level": level, "constellation": cons,
            "talents": skills, "crit_rate": crit_r, "crit_dmg": crit_d, "er": er,
            "weapon": weapon, "artifacts": len(arts),
            "artifact_avg": round(sum(a["level"] for a in arts) / len(arts), 1) if arts else 0,
            "findings": findings}


def audit_showcase(data):
    avatars = data.get("avatarInfoList") or []
    detailed = bool(avatars)
    chars = [audit_avatar(av) for av in avatars]
    preview = []
    for p in (data.get("playerInfo", {}).get("showAvatarInfoList") or []):
        avid = str(p.get("avatarId", "?"))
        meta = char_meta(avid)
        nm = (jmp_detail(meta["jmp"]).get("name") if meta["jmp"] else "") or f"Perso {avid}"
        preview.append({"id": avid, "name": nm, "level": p.get("level", 0),
                        "element": meta["element"], "rarity": meta["rarity"]})
    prio = []
    for c in chars:
        prio.extend(f"{c['name']} : {f}" for f in c["findings"])
    if not detailed:
        names = {c["name"] for c in preview}
        if {"Bennett", "Xiangling", "Xingqiu"} <= names:
            prio.append("Noyau 'National' détecté (Bennett/Xiangling/Xingqiu) : 4e slot Kaeya ou Yelan, team viable jusqu'à l'abysse.")
        if "Yelan" in names:
            prio.append("Yelan 5★ : excellent investissement long terme, monte-la avec Xingqiu en double Hydro.")
        tops = sorted(preview, key=lambda c: -c["level"])[:4]
        if tops and tops[0]["level"] < 60:
            prio.append(f"AR30 : concentre l'XP sur 4 mains ({', '.join(c['name'] for c in tops)}), "
                        "pas d'artefacts 5★ avant AR45.")
    return {"detailed": detailed, "characters": chars, "preview": preview, "priorities": prio}


def showcase_summary(data):
    p = data.get("playerInfo", {})
    a = audit_showcase(data)
    lines = [f"Joueur {p.get('nickname', '?')} AR{p.get('level', '?')} WL{p.get('worldLevel', '?')} "
             f"(succès: {p.get('finishAchievementNum', '?')})."]
    if not a["detailed"]:
        lines.append("Vitrine détaillée MASQUÉE : seuls les niveaux de la preview sont visibles. "
                     "Conseiller d'activer 'Afficher les détails des personnages'.")
        for c in a["preview"]:
            lines.append(f"- {c['name']} ({c['element']}) niv. {c['level']} {c['rarity']}★.")
    else:
        for c in a["characters"]:
            w = f"arme {c['weapon']['level']}" if c["weapon"] else "sans arme"
            cr = f" {c['crit_rate']:.0f}/{c['crit_dmg']:.0f}" if c["crit_rate"] else ""
            lines.append(f"- {c['name']} ({c['element']}) niv. {c['level']} C{c['constellation']}, "
                         f"{w}, {c['artifacts']}/5 artefacts moy. +{c['artifact_avg']}, crit{cr}.")
        if a["priorities"]:
            lines.append("Priorités détectées :")
            lines.extend(f"  * {x}" for x in a["priorities"][:12])
    return "\n".join(lines)


# ---------- Tavily (news / patch, gratuit tiers) ----------

def tavily_search(query, k=5):
    key = E("TAVILY_API_KEY", "")
    if not key:
        return {"answer": "", "results": []}
    try:
        d = _http_json("https://api.tavily.com/search", method="POST", timeout=10,
                       data={"api_key": key, "query": query, "max_results": max(1, min(8, k)),
                             "include_answer": True, "search_depth": "basic"})
    except Exception:
        return {"answer": "", "results": []}
    res = [{"title": r.get("title", ""), "url": r.get("url", ""),
            "snippet": (r.get("content", "") or "")[:400]}
           for r in d.get("results", [])]
    return {"answer": d.get("answer", ""), "results": res}


NEWS_RE = re.compile(r"patch|banni[eè]re|banner|maj|mise [aà] jour|version \d|abyss|abysse|"
                     r"[eé]v[eé]nement|event|code|redeem|tier.?list|nouveau perso|rerun|hoyolab",
                     re.IGNORECASE)


def maybe_news_context(question):
    if not NEWS_RE.search(question or ""):
        return ""
    r = tavily_search(f"Genshin Impact {question} patch notes Hoyolab", k=5)
    parts = []
    if r["answer"]:
        parts.append("Résumé web : " + r["answer"][:800])
    for x in r["results"][:4]:
        parts.append(f"- {x['title']} ({x['url']}) : {x['snippet'][:250]}")
    return "\n".join(parts)


def fandom_search(query, k=3):
    """Liens canoniques Fandom (sans clé, toujours dispo)."""
    try:
        q = urllib.parse.urlencode({"action": "query", "list": "search",
                                    "srsearch": query, "format": "json", "srlimit": max(1, min(5, k))})
        d = _http_json(f"https://genshin-impact.fandom.com/api.php?{q}", timeout=10)
        out = []
        for r in ((d.get("query") or {}).get("search") or [])[:k]:
            t = r.get("title", "")
            if t:
                out.append({"title": t,
                            "url": "https://genshin-impact.fandom.com/wiki/" + t.replace(" ", "_")})
        return out
    except Exception:
        return []


ADVICE_RE = re.compile(r"build|arme|artefact|artéfact|team|[eé]quipe|rotation|talent|"
                       r"constellation|monter|priorit[ée]|conseil|recommand|pull|reroll|tier|"
                       r"donjon|abysse|abyss|boss|farm|stat\b|stats|d[eé]g[aâ]ts|crit|recharge",
                       re.IGNORECASE)


def maybe_fact_context(question):
    """Contexte web pour fact-check des conseils : Tavily (si clé) + Fandom (toujours)."""
    q = question or ""
    parts = []
    news = maybe_news_context(q)
    if news:
        parts.append(news)
    if ADVICE_RE.search(q):
        box = {}
        t1 = threading.Thread(target=lambda: box.update(
            tavily=[tavily_search(f"Genshin Impact {q} build guide", k=5)]), daemon=True)
        t2 = threading.Thread(target=lambda: box.update(
            fandom=fandom_search(f"Genshin Impact {q}", k=3)), daemon=True)
        t1.start()
        t2.start()
        t1.join(12)
        t2.join(12)
        r = (box.get("tavily") or [{"answer": "", "results": []}])[0]
        if r["answer"]:
            parts.append("Vérif web : " + r["answer"][:800])
        for x in r["results"][:3]:
            parts.append(f"- {x['title']} ({x['url']}) : {x['snippet'][:250]}")
        for x in box.get("fandom") or []:
            parts.append(f"- Wiki Fandom : {x['title']} ({x['url']}) — à vérifier avant de conseiller.")
        if not r["answer"] and not r["results"]:
            for x in fandom_search(q, k=3):
                if x not in parts:
                    parts.append(f"- Wiki Fandom : {x['title']} ({x['url']})")
    return "\n".join(parts)


# ---------- LLM (OmniRoute dev / zen prod, cf. RunCoach coach.py:307) ----------

def _llm_headers(session_key=""):
    base = E("OMNIROUTE_BASE_URL") or ""
    key = E("OMNIROUTE_API_KEY", "")
    if "zen/go" in base:
        # opencode Go : abonnement payant, Bearer obligatoire, UA propre + session stable.
        return {"User-Agent": "GenshinCoach/1.0",
                "x-opencode-client": "genshincoach",
                "x-opencode-project": "genshincoach",
                "x-opencode-request": uuid.uuid4().hex,
                "x-opencode-session": session_key or uuid.uuid4().hex,
                "Authorization": f"Bearer {key}"}
    if "opencode.ai" in base:
        h = {"User-Agent": "opencode-cli/1.0.0", "x-opencode-client": "desktop",
             "x-opencode-project": "global",
             "x-opencode-request": uuid.uuid4().hex,
             "x-opencode-session": session_key or uuid.uuid4().hex}
        if key and key != "dummy-key":
            h["Authorization"] = f"Bearer {key}"
        return h
    return {"Authorization": f"Bearer {key}"}


def _responses_text(d):
    if isinstance(d.get("output_text"), str) and d["output_text"]:
        return d["output_text"]
    for item in d.get("output") or []:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    return c["text"]
    raise RuntimeError(f"Réponse Go inattendue : {str(d)[:200]}")


def _sse_post(url, data, headers, timeout=180):
    """POST SSE (stdlib) : yield chaque payload 'data:' (dict JSON ou str)."""
    body = json.dumps(data).encode()
    h = {"User-Agent": "GenshinCoach/1.0", "Content-Type": "application/json",
         "Accept": "text/event-stream", **(headers or {})}
    req = urllib.request.Request(url, data=body, method="POST", headers=h)
    resp = urllib.request.urlopen(req, timeout=timeout)
    event = []
    try:
        while True:
            line = resp.readline()
            if not line:
                break
            try:
                s = line.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if s == "":
                if event:
                    payload = "\n".join(event)
                    del event[:]
                    if payload == "[DONE]":
                        continue
                    try:
                        yield json.loads(payload)
                    except ValueError:
                        yield payload
                continue
            if s.startswith("data:"):
                event.append(s[5:].strip())
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _extract_delta(evt):
    """Tente d'extraire le bout de réponse d'un event SSE (2 formats supportés)."""
    if isinstance(evt, str):
        return evt
    if not isinstance(evt, dict):
        return ""
    if str(evt.get("type", "")).startswith("response.reasoning"):
        return ""  # résumé de raisonnement : géré par _extract_thinking, pas dans la réponse
    try:  # OpenAI /chat/completions : choices[0].delta.content
        ch = (evt.get("choices") or [{}])[0] or {}
        t = ((ch.get("delta") or {}).get("content")) or ch.get("text")
        if t:
            return t
    except Exception:
        pass
    # Responses API : {"type": "response.output_text.delta", "delta": "..."}
    if evt.get("type") == "response.output_text.delta" \
            and isinstance(evt.get("delta"), str) and evt["delta"]:
        return evt["delta"]
    return ""


def _extract_thinking(evt):
    """Résumé de raisonnement partageable (summary:auto), affichable dans l'UI."""
    if isinstance(evt, dict) and evt.get("type") == "response.reasoning_summary_text.delta" \
            and isinstance(evt.get("delta"), str):
        return evt["delta"]
    return ""


def _responses_summary(d):
    """Résumé de raisonnement d'une réponse non-streamée (batch)."""
    try:
        out = []
        for item in d.get("output") or []:
            if isinstance(item, dict) and item.get("type") == "reasoning":
                for part in item.get("summary") or []:
                    if isinstance(part, dict) and part.get("text"):
                        out.append(part["text"])
        return "\n".join(out)
    except Exception:
        return ""


def _reasoning_arg():
    """Effort de raisonnement (Responses API) : OMNIROUTE_REASONING_EFFORT=minimal|low|medium|high|xhigh.
    Défaut 'xhigh' + résumé partageable (summary:auto) pour afficher le train de pensée dans l'UI."""
    v = (E("OMNIROUTE_REASONING_EFFORT", "xhigh") or "").strip().lower()
    if v in ("minimal", "low", "medium", "high", "xhigh"):
        return {"reasoning": {"effort": v, "summary": "auto"}}
    return {}


def llm_stream(messages, session_key=""):
    """Yield ("thinking"|"answer", texte) au fil de l'eau. Repli batch si le stream échoue."""
    base = (E("OMNIROUTE_BASE_URL") or "").rstrip("/")
    model = E("OMNIROUTE_MODEL", "auto")
    if not base:
        raise RuntimeError("OMNIROUTE_BASE_URL manquant")
    if "zen/go" in base:
        url = base + "/responses"
        model_id = model.split("/", 1)[-1]  # opencode-go/x -> x
        data = {"model": model_id, "stream": True,
                "input": [{"role": m["role"], "content": m["content"]}
                          for m in messages if m.get("role") in ("system", "user", "assistant")]}
        data.update(_reasoning_arg())
    else:
        url = base + "/chat/completions"
        data = {"model": model, "stream": True, "messages": messages}
    got = False
    try:
        for evt in _sse_post(url, data, _llm_headers(session_key)):
            th = _extract_thinking(evt)
            if th:
                yield ("thinking", th)
                continue
            t = _extract_delta(evt)
            if t:
                got = True
                yield ("answer", t)
    except Exception:
        if got:
            return  # coupe mid-stream : le partiel est déjà affiché/sauvegardé
    if not got:  # stream vide ou incompatible : un seul bloc (le front gère pareil)
        answer, _, thinking = llm_complete(messages, session_key=session_key)
        if thinking:
            yield ("thinking", thinking)
        yield ("answer", answer)


def llm_complete(messages, session_key=""):
    base = (E("OMNIROUTE_BASE_URL") or "").rstrip("/")
    model = E("OMNIROUTE_MODEL", "auto")
    if not base:
        raise RuntimeError("OMNIROUTE_BASE_URL manquant")
    if "zen/go" in base:
        model_id = model.split("/", 1)[-1]  # opencode-go/x -> x
        payload = {"model": model_id, "stream": False,
                   "input": [{"role": m["role"], "content": m["content"]}
                             for m in messages if m.get("role") in ("system", "user", "assistant")]}
        payload.update(_reasoning_arg())
        d = _http_json(base + "/responses", method="POST", timeout=180,
                       headers=_llm_headers(session_key), data=payload)
        return _responses_text(d), model, _responses_summary(d)
    d = _http_json(base + "/chat/completions", method="POST", timeout=120,
                   headers=_llm_headers(session_key),
                   data={"model": model, "stream": False, "messages": messages})
    think = _responses_summary(d) if isinstance(d, dict) else ""
    try:
        return d["choices"][0]["message"]["content"], d.get("model", model), think
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Réponse LLM inattendue : {str(d)[:200]}")


SYSTEM = ("Tu es un coach Genshin Impact francophone pour un joueur adulte qui débute, "
          "ton simple et respectueux, sans jargon technique. "
          "Tu vois le compte du joueur via Enka (niveaux, armes, artefacts, talents) et un audit automatique. "
          "Règles : phrases courtes, mots courants. Si tu dois employer un terme technique "
          "(par ex. artefacts, recharge d'énergie, taux crit, constellation), donne aussitôt sa définition "
          "simple puis ce qu'il faut faire concrètement en jeu. "
          "Avant chaque conseil ou recommandation (build, arme, artefact, team, montée), appuie-toi sur "
          "les infos web et wiki Fandom fournies dans le contexte : ne contredis jamais le wiki, "
          "ne jamais inventer un perso, une arme ou un set. Si le contexte web est vide, reste sur "
          "l'audit Enka et dis-le franchement. "
          "Cite les vrais chiffres du joueur, priorise une seule action adaptée à son AR/WL. "
          "À AR30, pas de farm d'artefacts 5 étoiles avant l'AR45 : pense niveaux, armes, talents, "
          "statues, histoires et events. Propose des teams seulement avec ses persos, sauf un seul perso "
          "à aller chercher en plus. "
          "Si la vitrine détaillée est masquée, explique en phrases simples, sans liste : en jeu ouvre le menu Paimon "
          "avec Échap puis clique sur ta carte de profil puis sur le petit crayon en haut à droite puis sur "
          "l'onglet Vitrine puis ajoute tes persos et coche 'Afficher les détails des personnages'. "
          "Ne jamais inventer un autre chemin. "
          "Style obligatoire : 4 à 6 phrases courtes en texte simple, sans listes à puces, sans listes "
          "numérotées, sans tableaux, sans markdown compliqué.")


def build_messages(question, uid=None, history=None, showcase_text=None):
    """Construit les messages LLM (Enka + fact-check + historique). -> (msgs, detailed)."""
    uid = str(uid or DEFAULT_UID)
    t0 = time.time()
    box = {}

    def w_ctx():
        try:
            data = fetch_showcase(uid)
            box["ctx"] = showcase_text or showcase_summary(data)
            box["detailed"] = bool(data.get("avatarInfoList"))
        except Exception as ex:
            box["ctx"] = (f"Enka inaccessible pour UID {uid} : {ex}. "
                          "Conseiller en générique + vérifier UID/vitrine.")
            box["detailed"] = False

    def w_fact():
        box["fact"] = maybe_fact_context(question)

    t1 = threading.Thread(target=w_ctx, daemon=True)
    t2 = threading.Thread(target=w_fact, daemon=True)
    t1.start()
    t2.start()
    t1.join(30)
    t2.join(30)
    ctx = box.get("ctx") or f"Enka trop lent pour UID {uid}. Conseiller en générique."
    detailed = box.get("detailed", False)
    fact = box.get("fact") or ""
    print(f"TIMING ctx+fact={time.time()-t0:.1f}s (q={question[:40]!r})", flush=True)
    msgs = [{"role": "system", "content": SYSTEM + "\n\nCompte joueur (Enka) :\n" + ctx[:4000]}]
    if fact:
        msgs.append({"role": "system",
                     "content": "Infos fact-check (web + Fandom, à respecter) :\n" + fact[:2000]})
    for m in (history or [])[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            msgs.append({"role": m["role"], "content": m["content"][:2000]})
    msgs.append({"role": "user", "content": question})
    return msgs, detailed, ctx


def ask(question, uid=None, history=None, showcase_text=None, session_key=""):
    uid = str(uid or DEFAULT_UID)
    msgs, _, ctx = build_messages(question, uid=uid, history=history, showcase_text=showcase_text)
    try:
        answer, model, thinking = llm_complete(msgs, session_key=session_key or uid)
        return {"answer": answer, "model": model, "thinking": thinking, "llm": True}
    except Exception as ex:
        fall = ("Le LLM est injoignable (%s). En attendant, voici l'audit de ta vitrine :\n\n%s"
                % (ex, ctx[:3000]))
        return {"answer": fall, "model": "audit-only", "thinking": "", "llm": False}
