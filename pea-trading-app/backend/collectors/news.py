"""
collectors/news.py — Collecte des actualités via Finnhub API
Free tier : 60 req/min — mise en cache agressive 5 minutes
"""
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger

from backend.config import settings
from backend.cache.redis_client import cache_set, cache_get


FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# Mapping ticker Yahoo → ticker Finnhub (sans suffixe .PA etc.)
def _to_finnhub_ticker(ticker: str) -> str:
    """Convertit un ticker Yahoo Finance en ticker Finnhub."""
    # Euronext Paris : MC.PA → MC:EPA
    # Xetra : SAP.DE → SAP:XETRA
    # Amsterdam : ASML.AS → ASML:AMS
    mapping = {
        ".PA": ":EPA",
        ".DE": ":XETRA",
        ".AS": ":AMS",
    }
    for suffix, exchange in mapping.items():
        if ticker.endswith(suffix):
            base = ticker.replace(suffix, "")
            return f"{base}{exchange}"
    return ticker


async def fetch_news(ticker: str, days_back: int = 7) -> list[dict]:
    """
    Récupère les dernières news pour un ticker.
    Utilise le cache Redis 5 minutes pour éviter les rate limits.
    """
    if not settings.FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY non configurée, news désactivées")
        return []

    cache_key = f"news:{ticker}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    finnhub_ticker = _to_finnhub_ticker(ticker)
    today = datetime.now(timezone.utc)
    from_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{FINNHUB_BASE_URL}/company-news",
                params={
                    "symbol": finnhub_ticker,
                    "from": from_date,
                    "to": to_date,
                    "token": settings.FINNHUB_API_KEY,
                },
            )
            resp.raise_for_status()
            articles = resp.json()

        if not isinstance(articles, list):
            return []

        # Formater et limiter à 5 news récentes
        news = []
        for art in articles[:5]:
            sentiment_score = art.get("sentiment", {}).get("articleScore", 0)
            if isinstance(sentiment_score, (int, float)):
                sentiment = "POSITIVE" if sentiment_score > 0.1 else ("NEGATIVE" if sentiment_score < -0.1 else "NEUTRAL")
            else:
                sentiment = "NEUTRAL"
                sentiment_score = 0

            news.append({
                "ticker": ticker,
                "headline": art.get("headline", ""),
                "summary": art.get("summary", "")[:300] if art.get("summary") else "",
                "source": art.get("source", ""),
                "url": art.get("url", ""),
                "sentiment": sentiment,
                "sentiment_score": float(sentiment_score),
                "published_at": datetime.fromtimestamp(
                    art.get("datetime", 0), tz=timezone.utc
                ).isoformat(),
            })

        await cache_set(cache_key, news, ttl=settings.REDIS_CACHE_TTL_NEWS)
        return news

    except httpx.HTTPStatusError as e:
        logger.warning(f"Finnhub HTTP {e.response.status_code} pour {ticker}")
        return []
    except Exception as e:
        logger.error(f"Erreur news({ticker}): {e}")
        return []


async def fetch_market_sentiment() -> dict:
    """
    Récupère le sentiment général du marché (Fear & Greed index via Finnhub).
    """
    if not settings.FINNHUB_API_KEY:
        return {"sentiment": "NEUTRAL", "score": 50}

    cached = await cache_get("market:sentiment")
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{FINNHUB_BASE_URL}/news-sentiment",
                params={"symbol": "^STOXX50E", "token": settings.FINNHUB_API_KEY},
            )
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "sentiment": "POSITIVE" if data.get("bullishPercent", 50) > 55 else
                                 ("NEGATIVE" if data.get("bullishPercent", 50) < 45 else "NEUTRAL"),
                    "bull_pct": data.get("bullishPercent", 50),
                    "bear_pct": data.get("bearishPercent", 50),
                }
                await cache_set("market:sentiment", result, ttl=600)
                return result
    except Exception as e:
        logger.warning(f"Erreur market sentiment: {e}")

    return {"sentiment": "NEUTRAL", "score": 50}
