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

def tavily_search(query, k=5):
    key = E("TAVILY_API_KEY", "")
    if not key:
        return {"answer": "", "results": []}
    try:
        d = _http_json("https://api.tavily.com/search", method="POST", timeout=25,
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


# ---------- LLM (OmniRoute dev / zen prod, cf. RunCoach coach.py:307) ----------

def _llm_headers():
    base = E("OMNIROUTE_BASE_URL") or ""
    if "opencode.ai" in base:
        return {"User-Agent": "opencode-cli/1.0.0", "x-opencode-client": "desktop",
                "x-opencode-project": "global",
                "x-opencode-request": uuid.uuid4().hex,
                "x-opencode-session": uuid.uuid4().hex}
    return {"Authorization": f"Bearer {E('OMNIROUTE_API_KEY')}"}


def llm_complete(messages):
    base = (E("OMNIROUTE_BASE_URL") or "").rstrip("/")
    model = E("OMNIROUTE_MODEL", "auto")
    if not base:
        raise RuntimeError("OMNIROUTE_BASE_URL manquant")
    d = _http_json(base + "/chat/completions", method="POST", timeout=120,
                   headers=_llm_headers(),
                   data={"model": model, "stream": False, "messages": messages})
    try:
        return d["choices"][0]["message"]["content"], d.get("model", model)
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Réponse LLM inattendue : {str(d)[:200]}")


SYSTEM = ("Tu es un coach Genshin Impact francophone, direct et concret. "
          "Tu vois le compte du joueur via Enka (niveaux, armes, artefacts, talents) et un audit automatique. "
          "Règles : cite les chiffres réels du joueur ; priorise (1 chose à la fois, adaptée AR/WL) ; "
          "à AR30, le farm d'artefacts 5★ attendra l'AR45 — focus niveaux, armes, talents, archons/statues, "
          "histoires et events. Teams proposées uniquement avec son roster sauf +1 à pull ciblé. "
          "Si la vitrine détaillée est masquée, demande d'activer 'Afficher les détails des personnages' "
          "tout en conseillant sur la preview. Ne cite JAMAIS un personnage qui n'est pas dans sa vitrine. "
          "Réponses courtes, listes à puces, pas de blabla.")


def ask(question, uid=None, history=None, showcase_text=None):
    uid = str(uid or DEFAULT_UID)
    try:
        data = fetch_showcase(uid)
        ctx = showcase_text or showcase_summary(data)
    except Exception as ex:
        ctx = f"Enka inaccessible pour UID {uid} : {ex}. Conseiller en générique + vérifier UID/vitrine."
    news = maybe_news_context(question)
    msgs = [{"role": "system", "content": SYSTEM + "\n\nCompte joueur (Enka) :\n" + ctx[:4000]}]
    if news:
        msgs.append({"role": "system", "content": "Infos fraîches du web :\n" + news[:2000]})
    for m in (history or [])[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            msgs.append({"role": m["role"], "content": m["content"][:2000]})
    msgs.append({"role": "user", "content": question})
    try:
        answer, model = llm_complete(msgs)
        return {"answer": answer, "model": model, "llm": True}
    except Exception as ex:
        fall = ("Le LLM est injoignable (%s). En attendant, voici l'audit de ta vitrine :\n\n%s"
                % (ex, ctx[:3000]))
        return {"answer": fall, "model": "audit-only", "llm": False}
