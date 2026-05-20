"""
scheduler.py — Collecte périodique des données (toutes les 15 secondes)
Utilise APScheduler en mode AsyncIO
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
import asyncio

from backend.config import settings
from backend.collectors.market_data import collect_all
from backend.analysis.recommender import build_recommendations
from backend.cache.redis_client import publish, cache_set

scheduler = AsyncIOScheduler()
_last_data: dict = {}


async def _collect_and_broadcast():
    """Tâche principale : collecte + analyse + diffusion WebSocket."""
    global _last_data
    try:
        logger.debug("Début collecte données marché...")

        # 1. Collecte des données
        data = await collect_all()
        if not data:
            logger.warning("Collecte vide, pas de diffusion")
            return

        # 2. Publier les updates sur Redis pub/sub (pour les WebSockets)
        from datetime import datetime, timezone
        message = {
            "type": "quote_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                ticker: {
                    "price": d.get("price"),
                    "change": d.get("change"),
                    "change_pct": d.get("change_pct"),
                    "volume_ratio": d.get("volume_ratio"),
                    "signal": d.get("signal"),
                    "score": d.get("score"),
                }
                for ticker, d in data.items()
            },
        }
        await publish("market:updates", message)
        _last_data = data

        logger.debug(f"Collecte OK : {len(data)} tickers diffusés")

    except Exception as e:
        logger.error(f"Erreur dans _collect_and_broadcast: {e}")


async def _build_recommendations_job():
    """Tâche toutes les 2 minutes : construction des recommandations."""
    try:
        recs = await build_recommendations()
        logger.info(f"Recommandations mises à jour : {len(recs)} entrées")

        from datetime import datetime, timezone
        await publish("market:recommendations", {
            "type": "signal_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"count": len(recs), "top": recs[:5]},
        })
    except Exception as e:
        logger.error(f"Erreur _build_recommendations_job: {e}")


def start_scheduler():
    """Démarre le scheduler avec toutes les tâches."""
    # Collecte données toutes les 15 secondes
    scheduler.add_job(
        _collect_and_broadcast,
        trigger=IntervalTrigger(seconds=settings.REFRESH_INTERVAL_SECONDS),
        id="collect_market_data",
        name="Collecte données marché",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=10,
    )

    # Recommandations toutes les 2 minutes
    scheduler.add_job(
        _build_recommendations_job,
        trigger=IntervalTrigger(minutes=2),
        id="build_recommendations",
        name="Construction recommandations",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    scheduler.start()
    logger.info(f"Scheduler démarré — collecte toutes les {settings.REFRESH_INTERVAL_SECONDS}s")


def stop_scheduler():
    """Arrête le scheduler proprement."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler arrêté")
