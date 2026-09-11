"""GenshinCoach — logique métier : Enka + meta + LLM. Stdlib only."""
import json
import os
import re
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

# ---------- Tavily (news) + Fandom (wiki, sans clé) ----------

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


def _responses_usage(d):
    """Tokens réellement consommés (pour le tok/s affiché)."""
    try:
        u = (d.get("response") or {}).get("usage") or d.get("usage") or {}
        out = int(u.get("output_tokens") or 0)
        inp = int(u.get("input_tokens") or 0)
        return (out or None, inp or None)
    except (TypeError, ValueError):
        return (None, None)


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


def _reasoning_arg(override=None):
    """Effort de raisonnement (Responses API) : OMNIROUTE_REASONING_EFFORT=minimal|low|medium|high|xhigh.
    Défaut 'xhigh' + résumé partageable (summary:auto) pour afficher le train de pensée dans l'UI.
    `override` force un niveau (planification = 'minimal', rapide, pas cher).
    Défaut 'low' : xhigh = 15s+ de silence car les summaries ne streament pas."""
    v = ((override or E("OMNIROUTE_REASONING_EFFORT", "low")) or "").strip().lower()
    if v in ("minimal", "low", "medium", "high", "xhigh"):
        return {"reasoning": {"effort": v, "summary": "auto"}}
    return {}


SYSTEM = ("Tu es un coach Genshin Impact francophone pour un joueur adulte qui débute, "
          "ton simple et respectueux, sans jargon technique. "
          "Tu vois le compte du joueur via Enka (niveaux, armes, artefacts, talents) et un audit automatique. "
          "Règles : phrases courtes, mots courants. Si tu dois employer un terme technique "
          "(par ex. artefacts, recharge d'énergie, taux crit, constellation), donne aussitôt sa définition "
          "simple puis ce qu'il faut faire concrètement en jeu. "
          "Tu as des outils pour récupérer le vrai compte du joueur (Enka), les fiches persos, "
          "le web et le wiki : n'appelle que les outils utiles à la question, jamais à l'avance, "
          "via le mécanisme natif d'appel d'outils. "
          "Appuie-toi sur leurs résultats, ne contredis jamais le wiki, "
          "ne jamais inventer un perso, une arme ou un set, et n'affiche jamais de JSON brut "
          "ni de balises <function>/<parameter> dans ta réponse. Si un résultat d'outil manque "
          "ou est vide, dis-le franchement et fais au mieux avec le reste, sans inventer. "
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


# ---------- Agent autonome (logique RunCoach, tools natifs) ----------
# muse-spark est /responses-only : tools natifs via function_call.
# Dev (passerelle OmniRoute locale) reste en /chat/completions avec tools natifs chat.
# Boucle : 8 iters max, dédupe seen, synthèse forcée, sanitize + leak XML tolérant.

MAX_ITERS = 8
_TOOL_TRUNC = 3000
_STEP_PREVIEW = 300
_ERR_HINTS = ("erreur", "inconnu", "introuvable", "indisponible", "sans résultat")


def _sanitize_answer(s):
    """Strip leaked tool-call XML (<function>, <parameter>) that some models emit as text."""
    if not s or "<function" not in s.lower() and "<parameter" not in s.lower():
        return s or ""
    m = re.search(r"<\s*function\b", s, flags=re.IGNORECASE)
    if m:
        return s[:m.start()].strip()
    return s


def _extract_leaked_tool_calls(text):
    """Tolerant parser for XML-style leaked calls like <function=wiki_search> + <parameter=...>.
    Returns OpenAI-compatible tool_calls list or []."""
    if not text or "<function" not in text.lower():
        return []
    m = re.search(r"<\s*function\s*=?\s*\"?([a-zA-Z_][a-zA-Z0-9_]*)\b", text, flags=re.IGNORECASE)
    if not m:
        return []
    name = m.group(1)
    if name not in _TOOL_FNS:
        return []
    params = {}
    for pm in re.finditer(r"<\s*parameter\s*=?\s*\"?([a-zA-Z_][a-zA-Z0-9_]*)[^>]*>(.*?)"
                          r"(?=<\s*/?\s*(parameter|function)\b|$)",
                          text, flags=re.IGNORECASE | re.DOTALL):
        key = pm.group(1)
        val = pm.group(2) or ""
        val = re.sub(r"</\s*(parameter|function)\s*>.*", "", val, flags=re.IGNORECASE | re.DOTALL).strip()
        val = re.split(r"<\s*/?\s*function\b", val, flags=re.IGNORECASE)[0].strip()
        if key and val:
            params[key] = val
    return [{"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(params)}}]


def _tool_get_showcase(uid):
    data = fetch_showcase(uid)
    txt = showcase_summary(data)
    return txt[:2500], bool(data.get("avatarInfoList"))


def _tool_get_character(name):
    jmp_id = (name or "").strip().lower().replace(" ", "-")
    d = jmp_detail(jmp_id) if jmp_id else {}
    if not d:
        return f"Fiche perso introuvable pour '{name}'. Essaie wiki_search('{name}').", False
    bits = [f"{k} : {v}" for k, v in d.items() if v]
    return (f"Fiche {d.get('name', name)} — " + " | ".join(bits))[:_TOOL_TRUNC], False


def _tool_web_search(query):
    r = tavily_search(f"Genshin Impact {query}", k=5)
    parts = []
    if r.get("answer"):
        parts.append("Résumé web : " + r["answer"][:800])
    for x in (r.get("results") or [])[:3]:
        parts.append(f"- {x.get('title', '')} ({x.get('url', '')}) : {(x.get('snippet', '') or '')[:250]}")
    if not parts:
        return "Recherche web sans résultat (clé manquante ou aucun résultat).", False
    return "\n".join(parts)[:_TOOL_TRUNC], False


def _tool_wiki_search(query):
    res = fandom_search(query, k=3)
    if not res:
        return f"Wiki Fandom sans résultat pour '{query}'.", False
    return "\n".join(f"- Wiki Fandom : {x['title']} ({x['url']})" for x in res)[:_TOOL_TRUNC], False


def _t_showcase(_uid=None):
    txt, _ = _tool_get_showcase(_uid)
    return txt


def _t_character(name=""):
    txt, _ = _tool_get_character(name)
    return txt


def _t_web(query=""):
    txt, _ = _tool_web_search(query)
    return txt


def _t_wiki(query=""):
    txt, _ = _tool_wiki_search(query)
    return txt


_TOOL_FNS = {
    "get_showcase": _t_showcase,
    "get_character": _t_character,
    "web_search": _t_web,
    "wiki_search": _t_wiki,
}


def _run_tool(name, args, uid=None):
    try:
        fn = _TOOL_FNS[name]
    except KeyError:
        return f"outil inconnu: {name}"
    try:
        a2 = dict(args or {})
        if name == "get_showcase":
            a2["_uid"] = uid
        return str(fn(**a2))[:_TOOL_TRUNC] or "vide"
    except Exception as e:
        return f"outil {name} erreur: {e}"


def _tool_specs():
    return [
        {"type": "function", "function": {
            "name": "get_showcase",
            "description": "Compte Enka du joueur (niveaux, armes, artefacts, audit). UID déjà connu, aucun argument. Appelle-le pour personnaliser avec l'AR ou répondre compte/build/team/prio.",
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "get_character",
            "description": "Fiche perso (vision, arme, nation, description). Use quand la question porte sur un perso précis ou son histoire.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}}}, "required": ["name"]}},
        {"type": "function", "function": {
            "name": "web_search",
            "description": "Recherche web (patch, version, bannières, events, histoire récente). Use quand le joueur demande l'actu ou si le wiki ne suffit pas.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}}}, "required": ["query"]}},
        {"type": "function", "function": {
            "name": "wiki_search",
            "description": "Recherche wiki Fandom (lore, quêtes, chapitres, persos). Use pour histoire, lore, chapitre, quête.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}}}, "required": ["query"]}},
    ]


def _response_tools():
    out = []
    for s in _tool_specs():
        f = s.get("function") or {}
        out.append({"type": "function", "name": f.get("name"),
                    "description": f.get("description", ""),
                    "parameters": f.get("parameters") or {"type": "object", "properties": {}}})
    return out


def _use_responses():
    return "zen/go" in (E("OMNIROUTE_BASE_URL") or "")


def _model_id():
    model = E("OMNIROUTE_MODEL", "auto")
    if _use_responses():
        return model.split("/", 1)[-1]  # opencode-go/x -> x
    return model


def _build_msgs(question, uid=None, history=None):
    uid = str(uid or DEFAULT_UID)
    msgs = [{"role": "system", "content": SYSTEM + f"\n\nUID joueur : {uid}."}]
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": h["content"][:2000]})
    msgs.append({"role": "user", "content": question})
    return msgs, _tool_specs()


def _parse_tool_call(c):
    fn = c.get("function") or {}
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except Exception:
        args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        args_preview = json.dumps(args, default=str)[:200]
    except Exception:
        args_preview = ""
    return (fn.get("name") or "", args, args_preview)


def _step_error(name, out):
    if name not in _TOOL_FNS:
        return True
    low = (out or "").lower()
    return any(h in low for h in _ERR_HINTS)


# ----- Transport /chat/completions (dev local) -----

def _chat_complete(msgs, specs, session_key="", timeout=120):
    url = E("OMNIROUTE_BASE_URL").rstrip("/") + "/chat/completions"
    payload = {"model": _model_id(), "stream": False, "messages": msgs}
    if specs:
        payload["tools"] = specs
        payload["tool_choice"] = "auto"
    try:
        return _http_json(url, method="POST", timeout=timeout,
                          headers=_llm_headers(session_key), data=payload), False
    except Exception as e:
        if specs and "400" in str(e):  # modèle sans support tools -> one-shot
            payload = {"model": _model_id(), "stream": False, "messages": msgs}
            return _http_json(url, method="POST", timeout=timeout,
                              headers=_llm_headers(session_key), data=payload), True
        raise


def _chat_stream(msgs, specs, box, session_key="", timeout=120):
    """Stream OpenAI-compatible SSE. Yield token strings live, fills box{content,tcs,model}."""
    url = E("OMNIROUTE_BASE_URL").rstrip("/") + "/chat/completions"
    payload = {"model": _model_id(), "stream": True, "messages": msgs}
    if specs:
        payload["tools"] = specs
        payload["tool_choice"] = "auto"
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              **_llm_headers(session_key)})
        resp = urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        if specs and "400" in str(e):  # modèle sans support tools -> retry sans tools
            box["specs_fallback"] = True
            yield from _chat_stream(msgs, [], box, session_key, timeout)
            return
        raise
    content_parts, tc_acc, model_used = [], {}, _model_id()
    with resp:
        while True:
            line = resp.readline()
            if not line:
                break
            try:
                s = line.decode("utf-8", "replace").strip()
            except Exception:
                continue
            if not s or s.startswith(":") or not s.startswith("data:"):
                continue
            ds = s[5:].strip()
            if ds == "[DONE]":
                break
            try:
                chunk = json.loads(ds)
            except Exception:
                continue
            if chunk.get("model"):
                model_used = chunk["model"]
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                c = delta.get("content")
                if c:
                    content_parts.append(c)
                    yield c
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    ent = tc_acc.get(idx)
                    if ent is None:
                        ent = {"id": "", "name": "", "args": ""}
                        tc_acc[idx] = ent
                    if tc.get("id"):
                        ent["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        ent["name"] += fn["name"]
                    if fn.get("arguments"):
                        ent["args"] += fn["arguments"]
    tcs = [{"id": ent["id"] or ent["name"] or "tool_%d" % i, "type": "function",
            "function": {"name": ent["name"], "arguments": ent["args"] or "{}"}}
           for i, ent in sorted(tc_acc.items()) if ent["name"]]
    box.update(content="".join(content_parts), tcs=tcs, model=model_used)


# ----- Transport /responses (prod zen/go, muse-spark) -----

def _to_responses_input(msgs):
    items = []
    for m in msgs or []:
        r = m.get("role")
        if r == "system":
            items.append({"role": "system", "content": m.get("content", "")})
        elif r == "user":
            items.append({"role": "user", "content": m.get("content", "")})
        elif r == "assistant":
            if m.get("content"):
                items.append({"role": "assistant", "content": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                items.append({"type": "function_call",
                              "call_id": tc.get("id"),
                              "name": fn.get("name"),
                              "arguments": fn.get("arguments") or "{}"})
        elif r == "tool":
            items.append({"type": "function_call_output",
                          "call_id": m.get("tool_call_id"),
                          "output": m.get("content", "")})
    return items


def _responses_output_to_chat(d):
    text_parts, tcs = [], []
    for item in d.get("output") or []:
        t = item.get("type")
        if t == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    text_parts.append(c["text"])
        elif t == "function_call":
            args = item.get("arguments")
            if not isinstance(args, str):
                try:
                    args = json.dumps(args or {})
                except Exception:
                    args = "{}"
            tcs.append({"id": item.get("call_id") or item.get("id") or item.get("name"),
                        "type": "function",
                        "function": {"name": item.get("name"), "arguments": args}})
    return "".join(text_parts), tcs, _responses_summary(d)


def _responses_complete(msgs, specs, session_key="", timeout=180, reasoning=None):
    base = E("OMNIROUTE_BASE_URL").rstrip("/")
    payload = {"model": _model_id(), "stream": False, "input": _to_responses_input(msgs)}
    if specs:
        payload["tools"] = _response_tools()
        payload["tool_choice"] = "auto"
    payload.update(_reasoning_arg(reasoning))
    try:
        d = _http_json(base + "/responses", method="POST", timeout=timeout,
                       headers=_llm_headers(session_key), data=payload)
    except Exception as e:
        if specs and "400" in str(e):
            payload = {"model": _model_id(), "stream": False,
                       "input": _to_responses_input(msgs)}
            payload.update(_reasoning_arg(reasoning))
            d = _http_json(base + "/responses", method="POST", timeout=timeout,
                           headers=_llm_headers(session_key), data=payload)
            text, tcs, think = _responses_output_to_chat(d)
            return text, tcs, think, True
        raise
    text, tcs, think = _responses_output_to_chat(d)
    return text, tcs, think, False


def _responses_stream(msgs, specs, box, session_key="", timeout=180, reasoning=None):
    """Stream Responses SSE. Yield ("token",str)/("thinking",str), fills box."""
    base = E("OMNIROUTE_BASE_URL").rstrip("/")
    payload = {"model": _model_id(), "stream": True, "input": _to_responses_input(msgs)}
    if specs:
        payload["tools"] = _response_tools()
        payload["tool_choice"] = "auto"
    payload.update(_reasoning_arg(reasoning))
    try:
        stream = _sse_post(base + "/responses", payload, _llm_headers(session_key),
                           timeout=timeout)
        first = next(stream)
    except StopIteration:
        box.update(content="", tcs=[], thinking="", model=_model_id())
        return
        yield  # pragma: no cover - garde le générateur paresseux
    except Exception as e:
        if specs and "400" in str(e):
            box["specs_fallback"] = True
            yield from _responses_stream(msgs, [], box, session_key, timeout, reasoning)
            return
        raise
    content_parts, think_parts, calls, order = [], [], {}, []
    model_used, out_tokens = _model_id(), None

    def _feed(evt):
        nonlocal out_tokens
        if isinstance(evt, str):
            return None
        if not isinstance(evt, dict):
            return None
        if evt.get("model") and isinstance(evt.get("model"), str):
            nonlocal_model[0] = evt["model"]
        t = evt.get("type", "")
        if t == "response.output_text.delta" and isinstance(evt.get("delta"), str):
            content_parts.append(evt["delta"])
            return ("token", evt["delta"])
        th = _extract_thinking(evt)
        if th:
            think_parts.append(th)
            return ("thinking", th)
        if t == "response.output_item.added":
            item = evt.get("item") or {}
            if item.get("type") == "function_call":
                key = item.get("id") or item.get("call_id") or "call_%d" % len(order)
                if key not in calls:
                    calls[key] = {"id": item.get("call_id") or item.get("id") or "",
                                  "name": item.get("name") or "", "args": ""}
                    order.append(key)
            return None
        if t == "response.output_item.done":
            item = evt.get("item") or {}
            if item.get("type") == "function_call":
                key = item.get("id") or item.get("call_id") or (order[-1] if order else None)
                args = item.get("arguments")
                if key is not None:
                    if key not in calls:
                        calls[key] = {"id": "", "name": "", "args": ""}
                        order.append(key)
                    if item.get("name"):
                        calls[key]["name"] = item["name"]
                    if isinstance(args, str) and args:
                        calls[key]["args"] = args
            return None
        if t == "response.function_call_arguments.delta":
            a = evt.get("delta")
            if isinstance(a, str) and a and order:
                calls[order[-1]]["args"] += a
            return None
        if t == "response.incomplete":
            box["incomplete"] = True
            return None
        if t == "response.completed":
            resp = evt.get("response") or {}
            u = resp.get("usage") or evt.get("usage") or {}
            try:
                out_tokens = int(u.get("output_tokens") or 0) or None
            except (TypeError, ValueError):
                out_tokens = None
            return None
        try:  # repli format chat inattendu
            ch = (evt.get("choices") or [{}])[0] or {}
            d = ((ch.get("delta") or {}).get("content")) or ch.get("text")
        except Exception:
            d = ""
        if d:
            content_parts.append(d)
            return ("token", d)
        return None

    nonlocal_model = [model_used]
    try:
        r = _feed(first)
        if r:
            yield r
        for evt in stream:
            r = _feed(evt)
            if r:
                yield r
    except Exception as e:
        if specs and "400" in str(e):
            box["specs_fallback"] = True
            yield from _responses_stream(msgs, [], box, session_key, timeout, reasoning)
            return
        raise
    tcs = [{"id": calls[k]["id"] or calls[k]["name"] or "tool_%d" % i, "type": "function",
            "function": {"name": calls[k]["name"], "arguments": calls[k]["args"] or "{}"}}
           for i, k in enumerate(order) if calls[k]["name"]]
    box.update(content="".join(content_parts), tcs=tcs, thinking="".join(think_parts),
               model=nonlocal_model[0], out_tokens=out_tokens)


def _stream_turn(msgs, specs, box, session_key="", reasoning=None):
    if _use_responses():
        yield from _responses_stream(msgs, specs, box, session_key, reasoning=reasoning)
    else:
        yield from _chat_stream(msgs, specs, box, session_key)


def _turn_content_tcs(msgs, specs, session_key="", reasoning=None):
    """Un tour non-streamé -> (content, tcs, thinking, model, specs_fallback)."""
    if _use_responses():
        text, tcs, think, fell = _responses_complete(msgs, specs, session_key,
                                                     reasoning=reasoning)
        return text, tcs, think, _model_id(), fell
    data, fell = _chat_complete(msgs, specs, session_key)
    msg = data["choices"][0]["message"]
    return msg.get("content") or "", msg.get("tool_calls") or [], "",         data.get("model") or _model_id(), fell


# ----- Boucle agent -----

def _execute_calls(tcs, msgs, steps, seen, uid, content=""):
    """Exécute les tool_calls, alimente msgs/steps. -> detailed (True/False/None)."""
    detailed = None
    msgs.append({"role": "assistant", "content": content, "tool_calls": tcs})
    for c in tcs:
        name, args, args_preview = _parse_tool_call(c)
        t0 = time.time()
        key = (name, args_preview)
        if key in seen:
            out = seen[key]
            repeat = True
        else:
            out = _run_tool(name, args, uid)
            seen[key] = out
            repeat = False
        ms = int((time.time() - t0) * 1000)
        err = _step_error(name, out)
        steps.append({"tool": name, "args": args_preview, "result": out[:_STEP_PREVIEW],
                      "ms": ms, "error": err})
        if name == "get_showcase" and not err and "MASQUÉE" not in out:
            detailed = True
        if repeat:
            out = out + " [appel identique déjà effectué : réponds maintenant sans nouvel appel]"
        msgs.append({"role": "tool", "tool_call_id": c.get("id") or name or "tool",
                     "content": out[:_TOOL_TRUNC]})
    return detailed


def _audit_fallback_text(uid, err):
    try:
        data = fetch_showcase(uid)
        ctx = showcase_summary(data)
    except Exception:
        ctx = f"Enka inaccessible pour UID {uid}."
    return ("Le LLM est injoignable (%s). En attendant, voici l'audit de ta vitrine :\n\n%s"
            % (err, ctx[:3000]))


def ask(question, uid=None, history=None, showcase_text=None, session_key=""):
    uid = str(uid or DEFAULT_UID)
    t_all = time.time()
    msgs, specs = _build_msgs(question, uid, history)
    model = _model_id()
    answer, steps, thinking_parts = "", [], []
    seen = {}
    detailed = None
    incomplete_retry = False
    try:
        for _ in range(MAX_ITERS):
            content, tcs, thinking, model, fell = _turn_content_tcs(
                msgs, specs, session_key or uid, reasoning="minimal")
            if fell:
                specs = []
            if thinking:
                thinking_parts.append(thinking)
            if not tcs and not (content or "").strip():
                # tour vide (ex. response.incomplete) : 1 retry sans outils, réponse courte
                if not incomplete_retry:
                    incomplete_retry = True
                    specs = []
                    msgs.append({"role": "user",
                                 "content": "Ta réponse précédente a été coupée. Réponds "
                                            "brièvement en texte simple, sans outils."})
                    continue
            if not tcs and content:
                leaked = _extract_leaked_tool_calls(content)
                if leaked:
                    tcs = leaked
                    content = _sanitize_answer(content)
            if not tcs:
                answer = _sanitize_answer(content)
                break
            det = _execute_calls(tcs, msgs, steps, seen, uid, _sanitize_answer(content))
            if det:
                detailed = True
        else:
            synth = msgs + [{"role": "user",
                             "content": "Tu as atteint la limite d'outils. Réponds maintenant en texte "
                                        "clair, sans JSON brut ni balises <function>/<parameter>, en "
                                        "t'appuyant sur les résultats déjà obtenus."}]
            content, _, thinking, model, _ = _turn_content_tcs(synth, [], session_key or uid)
            if thinking:
                thinking_parts.append(thinking)
            answer = _sanitize_answer(content)
    except Exception as ex:
        if not answer:
            try:
                content, _, thinking, model, _ = _turn_content_tcs(
                    msgs + [{"role": "user",
                             "content": "DATA (fallback) :\n" + showcase_summary(fetch_showcase(uid))[:3000]}],
                    [], session_key or uid)
                if thinking:
                    thinking_parts.append(thinking)
                answer = _sanitize_answer(content)
            except Exception:
                pass
        if not answer:
            return {"answer": _audit_fallback_text(uid, ex), "model": "audit-only",
                    "thinking": "\n".join(thinking_parts), "steps": steps, "detailed": detailed,
                    "stats": {"total_s": round(time.time() - t_all, 1),
                              "llm_s": None, "out": None}, "llm": False}
    return {"answer": _sanitize_answer(answer), "model": model,
            "thinking": "\n".join(thinking_parts), "steps": steps, "detailed": detailed,
            "stats": {"total_s": round(time.time() - t_all, 1),
                      "llm_s": None, "out": None}, "llm": True}


def ask_stream(question, uid=None, history=None, session_key=""):
    """Générateur d'events 100% live: thinking/token au fil de l'eau, step_start
    avant chaque outil, step_end juste après, scratch si un brouillon doit être
    retiré (tour fini en tool_calls). Seule la réponse finale reste affichée."""
    uid = str(uid or DEFAULT_UID)
    msgs, specs = _build_msgs(question, uid, history)
    model = _model_id()
    steps, full, thinking_parts = [], "", []
    seen = {}
    detailed = None
    incomplete_retry = False
    try:
        for _ in range(MAX_ITERS):
            box = {}
            turn_text, turn_think, fwd = "", "", 0
            try:
                for kind, tok in _stream_turn(msgs, specs, box, session_key or uid,
                                              reasoning="minimal"):
                    if kind == "thinking":
                        turn_think += tok
                        yield {"type": "thinking", "delta": tok}
                    else:
                        turn_text += tok
                        fwd += len(tok)
                        yield {"type": "token", "delta": tok}
                if box.get("specs_fallback"):
                    specs = []
                tcs = box.get("tcs") or []
                model = box.get("model") or model
                content = _sanitize_answer(turn_text) if turn_text else ""
                if not tcs and turn_text:
                    leaked = _extract_leaked_tool_calls(turn_text)
                    if leaked:
                        tcs = leaked
                        content = _sanitize_answer(turn_text)
            except Exception as e:
                if specs and "400" in str(e):
                    specs = []
                    continue
                raise
            if turn_think:
                thinking_parts.append(turn_think)
            if not tcs and not (turn_text or "").strip():
                # tour vide (ex. response.incomplete) : 1 retry sans outils, réponse courte
                if not incomplete_retry:
                    incomplete_retry = True
                    specs = []
                    msgs.append({"role": "user",
                                 "content": "Ta réponse précédente a été coupée. Réponds "
                                            "brièvement en texte simple, sans outils."})
                    continue
            if tcs:
                if fwd > 0:  # retire le brouillon déjà peint
                    yield {"type": "scratch", "chars": fwd}
                msgs.append({"role": "assistant", "content": content, "tool_calls": tcs})
            else:
                if content != turn_text:
                    if fwd > 0:
                        yield {"type": "scratch", "chars": fwd}
                    if content:
                        yield {"type": "token", "delta": content}
                    full += content
                else:
                    full += turn_text
                break
            for c in tcs:
                name, args, args_preview = _parse_tool_call(c)
                yield {"type": "step_start", "tool": name, "args": args_preview}
                t0 = time.time()
                key = (name, args_preview)
                if key in seen:
                    out = seen[key]
                    repeat = True
                else:
                    out = _run_tool(name, args, uid)
                    seen[key] = out
                    repeat = False
                ms = int((time.time() - t0) * 1000)
                err = _step_error(name, out)
                steps.append({"tool": name, "args": args_preview, "result": out[:_STEP_PREVIEW],
                              "ms": ms, "error": err})
                yield {"type": "step_end", "tool": name, "args": args_preview,
                       "result": out[:_STEP_PREVIEW], "ms": ms, "error": err}
                if name == "get_showcase" and not err and "MASQUÉE" not in out:
                    detailed = True
                if repeat:
                    out = out + " [appel identique déjà effectué : réponds maintenant sans nouvel appel]"
                msgs.append({"role": "tool", "tool_call_id": c.get("id") or name or "tool",
                             "content": out[:_TOOL_TRUNC]})
        else:  # iters épuisées : synthèse forcée sans outils
            synth = msgs + [{"role": "user",
                             "content": "Tu as atteint la limite d'outils. Réponds maintenant en texte "
                                        "clair, sans JSON brut ni balises <function>/<parameter>, en "
                                        "t'appuyant sur les résultats déjà obtenus."}]
            box = {}
            turn_text = ""
            for kind, tok in _stream_turn(synth, [], box, session_key or uid):
                if kind == "thinking":
                    thinking_parts.append(tok)
                    yield {"type": "thinking", "delta": tok}
                else:
                    turn_text += tok
                    yield {"type": "token", "delta": tok}
            content = _sanitize_answer(turn_text)
            model = box.get("model") or model
            if content != turn_text and turn_text:
                yield {"type": "scratch", "chars": len(turn_text)}
                if content:
                    yield {"type": "token", "delta": content}
            full += content
        full = _sanitize_answer(full)
        yield {"type": "done", "answer": full, "model": model, "steps": steps,
               "thinking": "\n".join(x for x in thinking_parts if x), "detailed": detailed}
    except Exception as e:
        if not full:  # dernier recours : audit Enka plutôt qu'un 500
            try:
                fb = _audit_fallback_text(uid, e)
                yield {"type": "token", "delta": fb}
                yield {"type": "done", "answer": fb, "model": "audit-only", "steps": steps,
                       "thinking": "\n".join(x for x in thinking_parts if x), "detailed": detailed}
                return
            except Exception:
                pass
        yield {"type": "error", "error": str(e)}
