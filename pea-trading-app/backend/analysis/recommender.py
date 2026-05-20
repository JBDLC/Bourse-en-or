"""
analysis/recommender.py — Moteur de recommandations
Combine signaux techniques + analyses IA pour produire le top des opportunités
"""
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from backend.cache.redis_client import get_all_quotes, get_all_signals, cache_set, cache_get
from backend.analysis.news_analyzer import batch_analyze


async def build_recommendations() -> list[dict]:
    """
    Construit la liste des recommandations triées par score.
    1. Récupère tous les quotes et signaux depuis Redis
    2. Lance les analyses IA sur les tops candidats
    3. Fusionne et trie par score composite
    """
    quotes = await get_all_quotes()
    signals = await get_all_signals()

    if not quotes:
        logger.warning("Aucun quote disponible pour les recommandations")
        return []

    # Fusionner quotes + signaux
    merged = []
    for ticker, quote in quotes.items():
        signal_data = signals.get(ticker, {})
        merged.append({
            **quote,
            "signal": signal_data.get("signal", "NEUTRAL"),
            "score": signal_data.get("score", 50),
            "score_breakdown": signal_data.get("score_breakdown", {}),
            "indicators": signal_data.get("indicators", quote.get("indicators", {})),
        })

    # Lancer analyses IA sur les meilleurs candidats
    try:
        ai_analyses = await batch_analyze(merged)
    except Exception as e:
        logger.error(f"Erreur batch_analyze: {e}")
        ai_analyses = {}

    # Construire les recommandations finales
    recommendations = []
    for data in merged:
        ticker = data["ticker"]
        ai = ai_analyses.get(ticker)

        # Score final = technique 70% + IA 30% si disponible
        tech_score = data.get("score", 50)
        if ai:
            final_score = int(tech_score * 0.7 + ai["score"] * 0.3)
            final_signal = _merge_signals(data.get("signal", "NEUTRAL"), ai["signal"])
        else:
            final_score = tech_score
            final_signal = data.get("signal", "NEUTRAL")

        rec = {
            "ticker": ticker,
            "name": data.get("name", ticker),
            "price": data.get("price", 0),
            "change_pct": data.get("change_pct", 0),
            "signal": final_signal,
            "score": final_score,
            "cause": ai.get("cause") if ai else _default_cause(data),
            "opportunity": ai.get("opportunity") if ai else None,
            "risk": ai.get("risk") if ai else None,
            "horizon": ai.get("horizon") if ai else None,
            "ai_analyzed": bool(ai),
            "indicators": data.get("indicators", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        recommendations.append(rec)

    # Trier : BUY first, puis par score décroissant
    signal_order = {"STRONG_BUY": 0, "BUY": 1, "NEUTRAL": 2, "AVOID": 3, "STRONG_AVOID": 4}
    recommendations.sort(
        key=lambda r: (signal_order.get(r["signal"], 2), -r["score"])
    )

    # Mettre en cache
    await cache_set("recommendations:latest", recommendations, ttl=60)
    logger.info(f"Recommandations construites : {len(recommendations)} tickers")
    return recommendations


def _merge_signals(tech_signal: str, ai_signal: str) -> str:
    """Fusionne signal technique et signal IA."""
    order = {"STRONG_BUY": 0, "BUY": 1, "NEUTRAL": 2, "AVOID": 3, "STRONG_AVOID": 4}
    ai_mapped = {"BUY": "BUY", "HOLD": "NEUTRAL", "AVOID": "AVOID"}
    ai_norm = ai_mapped.get(ai_signal, "NEUTRAL")

    tech_rank = order.get(tech_signal, 2)
    ai_rank = order.get(ai_norm, 2)
    avg = (tech_rank + ai_rank) / 2

    if avg <= 0.5:
        return "STRONG_BUY"
    elif avg <= 1.5:
        return "BUY"
    elif avg <= 2.5:
        return "NEUTRAL"
    elif avg <= 3.5:
        return "AVOID"
    else:
        return "STRONG_AVOID"


def _default_cause(data: dict) -> Optional[str]:
    """Génère une cause par défaut basée sur les indicateurs techniques."""
    indicators = data.get("indicators", {})
    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_hist")
    volume_ratio = data.get("volume_ratio", 1.0)

    parts = []
    if rsi and rsi < 35:
        parts.append(f"RSI survendu ({rsi:.0f})")
    elif rsi and rsi > 70:
        parts.append(f"RSI suracheté ({rsi:.0f})")

    if macd_hist and macd_hist > 0:
        parts.append("MACD haussier")
    elif macd_hist and macd_hist < 0:
        parts.append("MACD baissier")

    if volume_ratio and volume_ratio > 1.5:
        parts.append(f"volumes x{volume_ratio:.1f}")

    return " · ".join(parts) if parts else "Analyse technique en cours"


async def get_top_opportunities(limit: int = 10) -> list[dict]:
    """Retourne les meilleures opportunités d'achat."""
    cached = await cache_get("recommendations:latest")
    if cached:
        buy_signals = [r for r in cached if r.get("signal") in ("STRONG_BUY", "BUY")]
        return buy_signals[:limit]

    recs = await build_recommendations()
    buy_signals = [r for r in recs if r.get("signal") in ("STRONG_BUY", "BUY")]
    return buy_signals[:limit]
