"""
main.py — Application FastAPI principale
WebSocket temps réel + API REST + gestion du cycle de vie
"""
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import redis.asyncio as aioredis

from backend.config import settings
from backend.scheduler import start_scheduler, stop_scheduler
from backend.cache.redis_client import (
    get_redis, close_redis, cache_get, get_all_quotes, get_all_signals,
    redis_ping, get_redis_diagnostic,
)
from backend.scheduler import collect_stats
from backend.collectors.market_data import fetch_indices, TICKER_NAMES
from backend.analysis.recommender import build_recommendations, get_top_opportunities


# ── Gestionnaire de connexions WebSocket ──────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS connecté — {len(self.active)} clients actifs")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WS déconnecté — {len(self.active)} clients actifs")

    async def broadcast(self, message: dict):
        if not self.active:
            return
        payload = json.dumps(message, default=str)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── Redis Pub/Sub listener ────────────────────────────────────────────────────

async def redis_listener():
    """Écoute Redis pub/sub et diffuse aux clients WebSocket connectés."""
    while True:
        try:
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe("market:updates", "market:recommendations")
            logger.info("Redis pub/sub abonné")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await manager.broadcast(data)
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.error(f"Redis listener erreur: {e}")
            await asyncio.sleep(5)  # reconnexion auto


# ── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Démarrage {settings.APP_NAME}...")

    ok = await redis_ping()
    if not ok:
        logger.warning(
            "Redis injoignable — vérifiez REDIS_URL (Upstash rediss://...). "
            "Mode mémoire local activé pour les cours."
        )

    # Démarrer le scheduler de collecte
    start_scheduler()
    from backend.scheduler import _collect_and_broadcast, _build_recommendations_job
    asyncio.create_task(_collect_and_broadcast())
    asyncio.create_task(_build_recommendations_job())

    # Démarrer le listener Redis en tâche de fond
    listener_task = asyncio.create_task(redis_listener())

    yield  # Application en cours

    # Arrêt propre
    listener_task.cancel()
    stop_scheduler()
    await close_redis()
    logger.info("Application arrêtée proprement")


# ── App FastAPI ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints REST ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    quotes = await get_all_quotes()
    redis_ok = await redis_ping()
    diag = get_redis_diagnostic()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": redis_ok,
        "redis_diagnostic": diag,
        "quotes_cached": len(quotes),
        "memory_quotes": diag.get("memory_quotes", 0),
        "collect": collect_stats,
        "hint": (
            "Si redis=false mais memory_quotes>0, l'app fonctionne sans Redis. "
            "Si les deux sont 0, la collecte yfinance échoue — voir les logs Render."
        ),
    }


@app.post("/api/admin/refresh")
async def force_refresh():
    """Force une collecte (utile après correction REDIS_URL)."""
    from backend.scheduler import _collect_and_broadcast
    await _collect_and_broadcast()
    quotes = await get_all_quotes()
    return {
        "quotes_cached": len(quotes),
        "collect": collect_stats,
        "redis": await redis_ping(),
        "redis_diagnostic": get_redis_diagnostic(),
    }


@app.get("/api/status")
async def status():
    """Diagnostic déploiement (collecte, Redis, cache)."""
    quotes = await get_all_quotes()
    return {
        "redis_ok": await redis_ping(),
        "quotes_cached": len(quotes),
        "collect": collect_stats,
        "tickers_configured": len(TICKER_NAMES),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/quotes")
async def get_quotes(category: Optional[str] = Query(None)):
    """Retourne tous les cours temps réel."""
    quotes = await get_all_quotes()
    if not quotes:
        raise HTTPException(503, detail="Données non disponibles, collecte en cours...")

    items = list(quotes.values())

    # Filtrage optionnel par catégorie
    if category:
        import json, os
        path = os.path.join(os.path.dirname(__file__), "tickers.json")
        with open(path) as f:
            tickers_data = json.load(f)
        cat_tickers = {t["ticker"] for t in tickers_data.get(category, [])}
        items = [q for q in items if q.get("ticker") in cat_tickers]

    return {
        "quotes": items,
        "count": len(items),
        "last_update": datetime.now(timezone.utc).isoformat(),
        "market_open": _is_market_open(),
    }


@app.get("/api/quotes/{ticker}")
async def get_quote(ticker: str):
    """Retourne le cours d'un ticker spécifique."""
    ticker = ticker.upper()
    data = await cache_get(f"quote:{ticker}")
    if not data:
        raise HTTPException(404, detail=f"Ticker {ticker} non trouvé ou données non disponibles")
    return data


@app.get("/api/signals")
async def get_signals():
    """Retourne tous les signaux techniques."""
    signals = await get_all_signals()
    items = list(signals.values())
    items.sort(key=lambda x: -x.get("score", 0))
    return {
        "signals": items,
        "count": len(items),
        "last_update": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/recommendations")
async def get_recommendations(limit: int = Query(20, le=50)):
    """Retourne les meilleures opportunités triées par score."""
    cached = await cache_get("recommendations:latest")
    if cached:
        return {
            "recommendations": cached[:limit],
            "count": len(cached[:limit]),
            "last_update": datetime.now(timezone.utc).isoformat(),
            "ai_analyses_count": sum(1 for r in cached if r.get("ai_analyzed")),
        }

    # Construire si pas en cache
    recs = await build_recommendations()
    return {
        "recommendations": recs[:limit],
        "count": len(recs[:limit]),
        "last_update": datetime.now(timezone.utc).isoformat(),
        "ai_analyses_count": sum(1 for r in recs if r.get("ai_analyzed")),
    }


@app.get("/api/indices")
async def get_indices():
    """Retourne les cours des indices de référence."""
    cached = await cache_get("indices:latest")
    if cached:
        return {"indices": cached}

    indices = await fetch_indices()
    from backend.cache.redis_client import cache_set
    await cache_set("indices:latest", indices, ttl=60)
    return {"indices": indices}


@app.get("/api/news/{ticker}")
async def get_news(ticker: str):
    """Retourne les dernières news pour un ticker."""
    from backend.collectors.news import fetch_news
    ticker = ticker.upper()
    news = await fetch_news(ticker)
    return {"ticker": ticker, "news": news, "count": len(news)}


# ── Watchlist (stockée en Redis, persistance simple) ─────────────────────────

@app.get("/api/watchlist")
async def get_watchlist():
    """Retourne la watchlist."""
    watchlist = await cache_get("watchlist:items") or []
    return {"watchlist": watchlist, "count": len(watchlist)}


@app.post("/api/watchlist")
async def add_to_watchlist(item: dict):
    """Ajoute un ticker à la watchlist."""
    ticker = item.get("ticker", "").upper()
    if not ticker:
        raise HTTPException(400, detail="ticker requis")

    if ticker not in TICKER_NAMES:
        raise HTTPException(400, detail=f"{ticker} non éligible PEA ou inconnu")

    from backend.cache.redis_client import cache_set
    watchlist = await cache_get("watchlist:items") or []

    # Éviter les doublons
    if any(w.get("ticker") == ticker for w in watchlist):
        raise HTTPException(409, detail=f"{ticker} déjà dans la watchlist")

    watchlist.append({
        "ticker": ticker,
        "name": TICKER_NAMES.get(ticker, ticker),
        "added_at": datetime.now(timezone.utc).isoformat(),
        "alert_above": item.get("alert_above"),
        "alert_below": item.get("alert_below"),
        "notes": item.get("notes"),
    })

    await cache_set("watchlist:items", watchlist, ttl=86400 * 365)
    return {"success": True, "ticker": ticker}


@app.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    """Retire un ticker de la watchlist."""
    ticker = ticker.upper()
    from backend.cache.redis_client import cache_set
    watchlist = await cache_get("watchlist:items") or []
    watchlist = [w for w in watchlist if w.get("ticker") != ticker]
    await cache_set("watchlist:items", watchlist, ttl=86400 * 365)
    return {"success": True}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket principal — diffuse les mises à jour en temps réel.
    Envoie un snapshot initial à la connexion, puis les updates toutes les 15s.
    """
    await manager.connect(websocket)
    try:
        # Envoyer un snapshot initial
        quotes = await get_all_quotes()
        signals = await get_all_signals()
        await websocket.send_json({
            "type": "snapshot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "quotes": {k: {
                    "price": v.get("price"),
                    "change_pct": v.get("change_pct"),
                    "signal": v.get("signal"),
                    "score": v.get("score"),
                } for k, v in quotes.items()},
                "market_open": _is_market_open(),
            },
        })

        # Maintenir la connexion ouverte (ping toutes les 30s)
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({
                "type": "ping",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {},
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        manager.disconnect(websocket)


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _is_market_open() -> bool:
    """Vérifie si les marchés européens sont ouverts (9h-17h30 UTC+1)."""
    now = datetime.now()
    # Lundi=0 ... Vendredi=4
    if now.weekday() >= 5:
        return False
    hour = now.hour
    return 8 <= hour < 17  # UTC approximatif
