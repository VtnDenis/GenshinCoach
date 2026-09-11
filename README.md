# GenshinCoach

Coach Genshin Impact perso : vitrine Enka + audit builds + chat LLM + news patch.
Inspiré de RunCoach (backend stdlib, front statique, deploy Render free).

## Lancer en local

```sh
python api/server.py   # http://127.0.0.1:8000 (ou $PORT)
```

Dev LLM = passerelle OmniRoute voisine (`http://localhost:20128`, `MODEL=auto`).
Prod Render = `https://opencode.ai/zen/v1` en direct, `MODEL=big-pickle`.

## Contrat API

```
GET  /api/health
GET  /api/showcase?uid=702342940
GET  /api/news?q=patch+notes&k=5
GET  /api/sessions?n=20
GET  /api/sessions/<id>/messages
DELETE /api/sessions/<id>
POST /api/chat {question,uid?,session_id?}
```

## Prérequis jeu

En jeu : profil (crayon) → vitrine 8 persos → cocher
« Afficher les détails des personnages », sinon audit limité à la preview.

## Deploy

Push sur `master` → auto-deploy Render (`python api/server.py`,
`healthCheckPath: /api/health`). État en Turso (FS éphémère).
