# 📈 Bourse en or

Application de trading temps réel pour PEA (Plan d'Épargne en Actions) — conçue pour Saxo Bank.

## 🚀 Démarrage rapide (dev local)

### Prérequis
- Python 3.11+
- Node.js 18+
- Docker Desktop (pour Redis + PostgreSQL)

### 1. Cloner et configurer
```bash
cd pea-trading-app

# Copier le template d'environnement
cp .env.example .env

# Éditer .env avec vos clés API :
# - ANTHROPIC_API_KEY (console.anthropic.com)
# - FINNHUB_API_KEY (finnhub.io — gratuit)
# - TWELVE_DATA_API_KEY (twelvedata.com — gratuit)
```

### 2. Démarrer Redis + PostgreSQL
```bash
docker-compose up -d
```

### 3. Backend Python
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 4. Frontend React (autre terminal)
```bash
cd frontend
npm install
npm run dev
```

### 5. Ouvrir l'app
→ http://localhost:5173

---

## 🌐 Déploiement sur Render.com

Guide pas-à-pas détaillé : voir `DEPLOY_RENDER.md`.

### Services gratuits à créer

#### A. Upstash Redis (gratuit pour dev)
1. Aller sur https://upstash.com/
2. Créer une base Redis (région Frankfurt)
3. Copier l'URL `rediss://...` → mettre dans `REDIS_URL` sur Render

#### B. Déploiement avec render.yaml
1. Pusher le code sur GitHub
2. Aller sur https://render.com/
3. **New → Blueprint** → connecter votre repo GitHub
4. Render détecte automatiquement `render.yaml`
5. Renseigner les variables d'env manquantes (`ANTHROPIC_API_KEY`, etc.)
6. Cliquer **Deploy**

### Variables à configurer sur Render
| Variable | Valeur | Où trouver |
|----------|--------|-----------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | console.anthropic.com |
| `FINNHUB_API_KEY` | `...` | finnhub.io |
| `TWELVE_DATA_API_KEY` | `...` | twelvedata.com |
| `REDIS_URL` | `rediss://...` | Upstash dashboard |
| `DATABASE_URL` | Auto-généré | Render (postgresql) |

---

## 🏗️ Architecture

```
Données marché (yfinance) ──┐
News (Finnhub) ─────────────┼→ Collector 15s → Redis → Signal Engine
                             │                        → News Analyzer (Claude)
                             │                        → Recommender (scores)
                             │                              │
                             └──────────────────────────────→ FastAPI + WebSocket
                                                                    │
                                                            React Dashboard (3 colonnes)
```

## 📊 Signaux techniques

| Signal | Condition |
|--------|-----------|
| STRONG_BUY | RSI < 35 + MACD haussier + Volume > 1.5x |
| BUY | Score > 65/100 |
| NEUTRAL | Score 40-65/100 |
| AVOID | Score < 25/100 |
| STRONG_AVOID | RSI > 75 + MACD baissier + Volume > 1.5x |

**Score composite :**
- RSI (30%) + MACD (25%) + Volume (20%) + Bollinger (15%) + Trend (10%)

## 🤖 IA (Claude)

Pour chaque ticker avec score ≥ 50, Claude analyse :
- Les dernières news Finnhub
- Les indicateurs techniques
- Et génère : cause du mouvement + opportunité + risque + horizon

## ⚠️ Avertissement

Cet outil est un **aide à la décision**, pas un conseil financier.
- Ne jamais investir plus que ce que vous pouvez vous permettre de perdre
- Les signaux techniques ne garantissent pas les performances futures
- Consultez un conseiller financier pour des décisions importantes

---

## 🛠️ Développement avec Cursor

Ce projet est conçu pour être développé avec Cursor AI.
Le fichier `.cursor/rules` contient toutes les instructions pour l'IA.

**Commandes Cursor utiles :**
- `Cmd+K` → modifier un fichier existant
- `Cmd+L` → chat avec Cursor
- `@codebase` → référencer tout le projet dans le chat

Pour ajouter une fonctionnalité, dites à Cursor :
> "Ajoute un panneau de graphique avec Recharts dans ChartView.jsx. Utilise l'endpoint /api/quotes/{ticker} pour récupérer l'historique."
