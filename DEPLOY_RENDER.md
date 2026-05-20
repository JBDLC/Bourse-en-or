# Deploy Render - Checklist complete

Ce projet se deploie sur Render avec **2 services Render + 1 base Postgres Render + 1 Redis Upstash**.

## 1) Ce que tu dois deployer exactement

- **Web Service (Python)** : backend FastAPI
- **Static Site (Node build + static hosting)** : frontend React/Vite
- **PostgreSQL Render** : base SQL managée
- **Redis Upstash (externe a Render)** : cache + pub/sub temps reel

## 2) Type de services Render

- Backend: `Web Service` (runtime Python)
- Frontend: `Static Site` (build React puis publication dossier `dist`)
- SQL: `PostgreSQL` (managed database Render)

Le fichier `render.yaml` est deja configure pour un deploy Blueprint de ces 3 ressources Render.

## 3) Variables d'environnement a renseigner

### Backend (`pea-trading-backend`)

- `REDIS_URL` -> URL Upstash (`rediss://...`)
- `FINNHUB_API_KEY` -> cle Finnhub
- `TWELVE_DATA_API_KEY` -> cle Twelve Data
- `ANTHROPIC_API_KEY` -> cle Claude (optionnelle, recommandee)
- `ALLOWED_ORIGINS` -> deja defini dans `render.yaml`
- `DATABASE_URL` -> injecte automatiquement via `fromDatabase`

### Frontend (`pea-trading-frontend`)

- `VITE_API_URL` -> URL publique backend (deja dans `render.yaml`)
- `VITE_WS_URL` -> URL websocket backend (deja dans `render.yaml`)

## 4) Procedure simple (Blueprint)

1. Push le repo sur GitHub.
2. Dans Render: `New` -> `Blueprint`.
3. Connecte le repo et confirme le fichier `render.yaml`.
4. Render cree:
   - `pea-trading-backend`
   - `pea-trading-frontend`
   - `pea-trading-db`
5. Renseigne les variables `sync: false` (cles API + Redis).
6. Lance le deploy.

## 5) Verification post-deploy

- Backend health: `https://<backend>.onrender.com/api/health`
- Frontend: `https://<frontend>.onrender.com`
- Test API: `https://<backend>.onrender.com/api/quotes`
- WebSocket: verifie l'etat `LIVE` dans l'UI

## 6) Erreur build pandas / Python 3.14

Si le build echoue sur la compilation de `pandas` avec `cpython-314`, Render utilise Python 3.14 par defaut.
Le projet impose **Python 3.11.9** via `runtime.txt` et `PYTHON_VERSION` dans `render.yaml`.
Push ces fichiers puis redeploy.

## 7) Recommandations de production

- **Plan**: les plans free conviennent pour test/dev, mais peuvent "sleep".
- **Redis**: garde Upstash en region proche (Frankfurt) pour latence reduite.
- **Secrets**: ne jamais commiter `.env`.
- **IA optionnelle**: sans `ANTHROPIC_API_KEY`, l'app tourne en mode technique seul (pas de resume IA).

