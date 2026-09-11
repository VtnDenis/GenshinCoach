const $ = (id) => document.getElementById(id);
const uidEl = $("uid"), chatEl = $("chat"), modelEl = $("model");
let sessionId = "";
uidEl.value = localStorage.getItem("gc:uid") || "702342940";

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
}
function bubble(role, text) {
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.textContent = text;
  chatEl.appendChild(d);
  chatEl.scrollTop = chatEl.scrollHeight;
  return d;
}

async function loadShowcase() {
  const uid = uidEl.value.trim();
  localStorage.setItem("gc:uid", uid);
  $("player").textContent = "Chargement…";
  $("chars").innerHTML = ""; $("prio").innerHTML = "";
  try {
    const r = await fetch("/api/showcase?uid=" + encodeURIComponent(uid));
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    $("player").textContent = `${d.player.nickname} — AR${d.player.level} WL${d.player.worldLevel}`;
    const list = d.detailed ? d.characters : d.preview;
    $("chars").innerHTML = list.map((c) =>
      `<li><b>${esc(c.name)} · niv. ${c.level} · ${c.rarity}★</b>` +
      `<small>${esc(c.element || "")}${c.crit_rate ? ` · crit ${c.crit_rate.toFixed(0)}/${c.crit_dmg.toFixed(0)}` : ""}` +
      `${c.findings && c.findings.length ? ` · ${c.findings.length} point(s)` : ""}</small></li>`
    ).join("") || "<li>Aucun perso en vitrine.</li>";
    $("prio").innerHTML = (d.priorities || []).slice(0, 12).map((p) => `<li>${esc(p)}</li>`).join("") ||
      "<li>Rien à signaler pour l'instant.</li>";
    $("nodetail").hidden = d.detailed;
  } catch (e) {
    $("player").textContent = "Erreur : " + e.message;
  }
}

$("refresh").onclick = loadShowcase;
$("newchat").onclick = () => { sessionId = ""; chatEl.innerHTML = ""; modelEl.textContent = ""; };

$("form").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  $("q").value = "";
  bubble("user", q);
  const wait = bubble("assistant", "…");
  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q, uid: uidEl.value.trim(), session_id: sessionId}),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    wait.textContent = d.answer;
    sessionId = d.session_id || sessionId;
    modelEl.textContent = "modèle : " + (d.model || "?");
    chatEl.scrollTop = chatEl.scrollHeight;
  } catch (err) {
    wait.textContent = "Erreur : " + err.message;
  }
};

$("newsform").onsubmit = async (e) => {
  e.preventDefault();
  $("news").innerHTML = "<li>Recherche…</li>";
  try {
    const r = await fetch("/api/news?q=" + encodeURIComponent($("nq").value) + "&k=5");
    const d = await r.json();
    const items = (d.results || []).map((x) =>
      `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a><br><small>${esc(x.snippet || "")}</small></li>`
    ).join("");
    $("news").innerHTML = (d.answer ? `<li><b>Résumé :</b> ${esc(d.answer)}</li>` : "") + items || "<li>Rien trouvé.</li>";
  } catch (err) {
    $("news").innerHTML = "<li>Erreur : " + esc(err.message) + "</li>";
  }
};

loadShowcase();
