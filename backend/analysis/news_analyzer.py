"""
analysis/news_analyzer.py — Analyse des news via Claude API
Génère : cause du mouvement, opportunité, risque, signal IA
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional
import anthropic
from loguru import logger

from backend.config import settings, CLAUDE_SYSTEM_PROMPT
from backend.cache.redis_client import cache_set, cache_get


_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
    return _anthropic_client


async def analyze_ticker(
    ticker: str,
    name: str,
    price: float,
    change_pct: float,
    rsi: Optional[float],
    macd_hist: Optional[float],
    technical_signal: str,
    technical_score: int,
    news: list[dict],
) -> Optional[dict]:
    """
    Appelle Claude pour analyser un ticker et générer une recommandation.
    Retourne un dict JSON ou None en cas d'erreur.
    """
    # Cache 15 minutes pour éviter les appels redondants
    cache_key = f"ai_analysis:{ticker}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Claude désactivé si clé absente (mode dégradé propre)
    if not settings.ANTHROPIC_API_KEY:
        return None

    # Ne pas appeler Claude si le score technique est trop faible
    if technical_score < settings.AI_ANALYSIS_MIN_SCORE and technical_signal == "NEUTRAL":
        return None

    # Préparer le contexte pour Claude
    news_context = ""
    if news:
        headlines = [n["headline"] for n in news[:3]]
        news_context = f"\nDernières news :\n" + "\n".join(f"- {h}" for h in headlines)

    rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
    macd_hist_str = f"{macd_hist:.3f}" if macd_hist is not None else "N/A"

    user_prompt = f"""Ticker : {ticker} ({name})
Prix actuel : {price:.2f}€
Variation du jour : {change_pct:+.2f}%
Signal technique : {technical_signal} (score {technical_score}/100)
RSI 14 : {rsi_str}
MACD histogramme : {macd_hist_str}
{news_context}

Génère ton analyse JSON."""

    # Retry avec backoff
    for attempt in range(settings.CLAUDE_RETRY_COUNT + 1):
        try:
            client = get_client()
            response = await asyncio.wait_for(
                client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=settings.CLAUDE_MAX_TOKENS,
                    system=CLAUDE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                ),
                timeout=settings.CLAUDE_TIMEOUT,
            )

            raw = response.content[0].text.strip()

            # Nettoyer le JSON (enlever éventuels backticks)
            raw = raw.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(raw)

            # Valider les champs requis
            required = ["signal", "score", "cause", "opportunity", "risk", "horizon"]
            if not all(k in analysis for k in required):
                raise ValueError(f"Champs manquants dans la réponse Claude: {raw}")

            result = {
                "ticker": ticker,
                "signal": analysis["signal"],
                "score": int(analysis["score"]),
                "cause": analysis["cause"][:120],
                "opportunity": analysis["opportunity"][:150],
                "risk": analysis["risk"][:120],
                "horizon": analysis["horizon"],
                "ai_analyzed": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await cache_set(cache_key, result, ttl=900)  # 15 min
            logger.info(f"IA analysé {ticker}: {result['signal']} score={result['score']}")
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Claude timeout pour {ticker} (tentative {attempt+1})")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON invalide de Claude pour {ticker}: {e}")
        except Exception as e:
            logger.error(f"Erreur Claude pour {ticker}: {e}")

        if attempt < settings.CLAUDE_RETRY_COUNT:
            await asyncio.sleep(2 ** attempt)  # backoff exponentiel

    return None


async def batch_analyze(tickers_data: list[dict]) -> dict:
    """
    Lance des analyses IA en parallèle (max 3 simultanées pour ne pas saturer).
    Retourne un dict {ticker: analysis}.
    """
    from backend.collectors.news import fetch_news

    semaphore = asyncio.Semaphore(3)
    results = {}

    async def analyze_one(data: dict):
        async with semaphore:
            news = await fetch_news(data["ticker"])
            analysis = await analyze_ticker(
                ticker=data["ticker"],
                name=data.get("name", data["ticker"]),
                price=data.get("price", 0),
                change_pct=data.get("change_pct", 0),
                rsi=data.get("indicators", {}).get("rsi_14"),
                macd_hist=data.get("indicators", {}).get("macd_hist"),
                technical_signal=data.get("signal", "NEUTRAL"),
                technical_score=data.get("score", 50),
                news=news,
            )
            if analysis:
                results[data["ticker"]] = analysis

    # Filtrer : uniquement les tickers avec un signal fort
    interesting = [
        d for d in tickers_data
        if d.get("signal") in ("STRONG_BUY", "BUY", "STRONG_AVOID")
        or d.get("score", 0) >= settings.AI_ANALYSIS_MIN_SCORE
    ]

    await asyncio.gather(*[analyze_one(d) for d in interesting[:20]])
    logger.info(f"Analyses IA : {len(results)}/{len(interesting)} réussies")
    return results
