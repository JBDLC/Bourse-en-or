# Architecture — PEA Trading Companion

## Structure complète

```
pea-trading-app/
├── .cursor/
│   └── rules                    ← Instructions pour Cursor AI
├── backend/
│   ├── main.py                  ← FastAPI app, WebSocket, CORS
│   ├── scheduler.py             ← APScheduler, collecte toutes les 15s
│   ├── config.py                ← Paramètres, variables d'env
│   ├── tickers.json             ← Liste des tickers PEA éligibles
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── market_data.py       ← yfinance + Twelve Data
│   │   └── news.py              ← Finnhub news fetcher
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── signals.py           ← RSI, MACD, Bollinger, Volume signals
│   │   ├── news_analyzer.py     ← Sentiment + analyse via Claude API
│   │   └── recommender.py       ← Score composite, ranking opportunités
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py          ← SQLAlchemy engine, session
│   │   └── schemas.py           ← Pydantic models (Quote, Signal, Alert...)
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis_client.py      ← Redis get/set/publish helpers
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── quotes.py            ← GET /api/quotes
│   │   ├── signals.py           ← GET /api/signals
│   │   ├── recommendations.py   ← GET /api/recommendations
│   │   └── watchlist.py         ← CRUD /api/watchlist
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    ← Layout principal 3 colonnes
│   │   │   ├── MarketOverview.jsx ← Indices CAC40, Euro Stoxx, DAX
│   │   │   ├── OpportunityList.jsx ← Top opportunités scorées
│   │   │   ├── ChartView.jsx    ← Graphique prix + indicateurs
│   │   │   ├── SignalBadge.jsx  ← Badge coloré BUY/HOLD/AVOID
│   │   │   ├── NewsPanel.jsx    ← Causes des mouvements (IA)
│   │   │   ├── Watchlist.jsx    ← Liste perso + alertes
│   │   │   ├── AlertConfig.jsx  ← Config seuils d'alerte
│   │   │   └── ConnectionStatus.jsx ← Indicateur WebSocket
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js  ← Hook WS avec reconnexion auto
│   │   │   ├── useQuotes.js     ← Fetch + cache cours
│   │   │   └── useSignals.js    ← Fetch + cache signaux
│   │   └── utils/
│   │       ├── formatters.js    ← Format prix, %, dates
│   │       └── colors.js        ← Couleurs selon signal/variation
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── render.yaml                  ← Config déploiement Render.com
├── docker-compose.yml           ← Dev local (Redis + Postgres)
├── .env.example                 ← Template variables d'environnement
└── README.md                    ← Guide installation et démarrage
```

## Flux de données

```
[APIs externes] → [Collectors 15s] → [Redis cache]
                                          ↓
                              [Signal Engine + News Analyzer]
                                          ↓
                              [Recommender → scores 0-100]
                                          ↓
                              [FastAPI REST + WebSocket]
                                          ↓
                              [React Dashboard temps réel]
```

## Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | /api/quotes | Tous les cours temps réel |
| GET | /api/quotes/{ticker} | Cours d'un ticker |
| GET | /api/signals | Tous les signaux techniques |
| GET | /api/recommendations | Top 10 opportunités triées |
| GET | /api/watchlist | Ma liste de suivi |
| POST | /api/watchlist | Ajouter un ticker |
| DELETE | /api/watchlist/{ticker} | Retirer un ticker |
| POST | /api/alerts | Créer une alerte de prix |
| WS | /ws | Stream temps réel (quotes + signals) |

## Modèles de données principaux

### Quote
```json
{
  "ticker": "MC.PA",
  "name": "LVMH",
  "price": 752.40,
  "change": 1.23,
  "change_pct": 0.164,
  "volume": 412500,
  "volume_avg_20d": 380000,
  "high_52w": 904.60,
  "low_52w": 601.20,
  "timestamp": "2025-05-20T14:32:00Z"
}
```

### Signal
```json
{
  "ticker": "MC.PA",
  "signal": "BUY",
  "score": 72,
  "rsi_14": 38.4,
  "macd": 2.14,
  "macd_signal": 1.87,
  "bb_position": 0.28,
  "volume_ratio": 1.34,
  "trend_1w": "UP",
  "timestamp": "2025-05-20T14:32:00Z"
}
```

### Recommendation
```json
{
  "ticker": "MC.PA",
  "name": "LVMH",
  "signal": "BUY",
  "score": 72,
  "cause": "Rebond sur support + hausse volumes institutionnels",
  "opportunity": "Setup technique favorable, objectif +2.5% sous 2j",
  "risk": "Résistance à 760€, sortir si cassure sous 745€",
  "horizon": "2j",
  "ai_analyzed": true,
  "timestamp": "2025-05-20T14:32:00Z"
}
```
