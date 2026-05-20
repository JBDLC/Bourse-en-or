"""
collectors/market_data.py — Collecte des cours et indicateurs techniques
Utilise yfinance (gratuit) comme source principale
Twelve Data API en complément pour les indicateurs temps réel
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional
import yfinance as yf
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from loguru import logger

from backend.config import settings
from backend.cache.redis_client import cache_set, cache_get
from backend.models.schemas import Quote, TechnicalIndicators, Signal, SignalType


def _load_tickers() -> list[dict]:
    """Charge la liste complète des tickers depuis tickers.json."""
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tickers.json")
    with open(path) as f:
        data = json.load(f)
    tickers = []
    for category in ["cac40", "midcap_paris", "europe_pea", "etf_pea"]:
        tickers.extend(data.get(category, []))
    return tickers[: settings.MAX_TICKERS]


TICKERS = _load_tickers()
TICKER_NAMES = {t["ticker"]: t["name"] for t in TICKERS}


def _compute_signal(rsi: Optional[float], macd_hist: Optional[float],
                    volume_ratio: Optional[float], bb_pos: Optional[float],
                    trend: Optional[str]) -> tuple[SignalType, int, dict]:
    """
    Calcule le signal composite et le score 0-100.
    Retourne (signal, score, breakdown).
    """
    scores = {}

    # RSI (30 points max)
    if rsi is not None:
        if rsi < settings.RSI_STRONG_BUY:
            scores["rsi"] = 30
        elif rsi < settings.RSI_BUY:
            scores["rsi"] = 22
        elif rsi < 55:
            scores["rsi"] = 15
        elif rsi < settings.RSI_AVOID:
            scores["rsi"] = 8
        else:
            scores["rsi"] = 0
    else:
        scores["rsi"] = 15  # neutre si absent

    # MACD histogram (25 points max)
    if macd_hist is not None:
        if macd_hist > 0.5:
            scores["macd"] = 25
        elif macd_hist > 0:
            scores["macd"] = 18
        elif macd_hist > -0.3:
            scores["macd"] = 10
        else:
            scores["macd"] = 0
    else:
        scores["macd"] = 12

    # Volume (20 points max)
    if volume_ratio is not None:
        if volume_ratio > settings.VOLUME_SPIKE_RATIO:
            scores["volume"] = 20
        elif volume_ratio > 1.2:
            scores["volume"] = 14
        elif volume_ratio > 0.8:
            scores["volume"] = 10
        else:
            scores["volume"] = 4
    else:
        scores["volume"] = 10

    # Bollinger position (15 points max) — 0=support inf, 1=résistance sup
    if bb_pos is not None:
        if bb_pos < 0.2:
            scores["bollinger"] = 15
        elif bb_pos < 0.4:
            scores["bollinger"] = 11
        elif bb_pos < 0.6:
            scores["bollinger"] = 7
        elif bb_pos < 0.8:
            scores["bollinger"] = 3
        else:
            scores["bollinger"] = 0
    else:
        scores["bollinger"] = 7

    # Trend (10 points max)
    if trend == "UP":
        scores["trend"] = 10
    elif trend == "FLAT":
        scores["trend"] = 5
    else:
        scores["trend"] = 0

    total_score = sum(scores.values())

    # Détermination du signal
    if rsi is not None and rsi < settings.RSI_STRONG_BUY and macd_hist is not None and macd_hist > 0 and volume_ratio is not None and volume_ratio > settings.VOLUME_SPIKE_RATIO:
        signal: SignalType = "STRONG_BUY"
    elif total_score >= 65:
        signal = "BUY"
    elif total_score >= 40:
        signal = "NEUTRAL"
    elif rsi is not None and rsi > settings.RSI_STRONG_AVOID and macd_hist is not None and macd_hist < 0 and volume_ratio is not None and volume_ratio > settings.VOLUME_SPIKE_RATIO:
        signal = "STRONG_AVOID"
    elif total_score < 25:
        signal = "AVOID"
    else:
        signal = "NEUTRAL"

    return signal, min(total_score, 100), scores


async def fetch_ticker_data(ticker: str) -> Optional[dict]:
    """
    Récupère cours + indicateurs pour un ticker.
    Retourne un dict complet ou None en cas d'erreur.
    """
    try:
        # Vérifier cache Redis d'abord
        cached = await cache_get(f"quote:{ticker}")
        if cached:
            return cached

        # Téléchargement données via yfinance (dans un thread pour ne pas bloquer)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(
                ticker,
                period=settings.YFINANCE_PERIOD,
                interval=settings.YFINANCE_INTERVAL,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        )

        if df is None or df.empty or len(df) < 20:
            logger.warning(f"Données insuffisantes pour {ticker}")
            return None

        # Aplatir colonnes multi-index si nécessaire
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].dropna()
        volume = df["Volume"].dropna()

        if len(close) < 20:
            return None

        # ── Cours actuels ──
        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price * 100) if prev_price != 0 else 0

        current_volume = int(volume.iloc[-1]) if not volume.empty else 0
        avg_volume = int(volume.tail(20).mean()) if len(volume) >= 20 else current_volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # ── Indicateurs techniques ──
        rsi_indicator = RSIIndicator(close=close, window=settings.RSI_PERIOD)
        rsi = float(rsi_indicator.rsi().iloc[-1])

        macd_indicator = MACD(
            close=close,
            window_fast=settings.MACD_FAST,
            window_slow=settings.MACD_SLOW,
            window_sign=settings.MACD_SIGNAL,
        )
        macd_val = float(macd_indicator.macd().iloc[-1])
        macd_sig = float(macd_indicator.macd_signal().iloc[-1])
        macd_hist = float(macd_indicator.macd_diff().iloc[-1])

        bb_indicator = BollingerBands(
            close=close,
            window=settings.BB_PERIOD,
            window_dev=settings.BB_STD,
        )
        bb_upper = float(bb_indicator.bollinger_hband().iloc[-1])
        bb_lower = float(bb_indicator.bollinger_lband().iloc[-1])
        bb_middle = float(bb_indicator.bollinger_mavg().iloc[-1])
        bb_range = bb_upper - bb_lower
        bb_position = (current_price - bb_lower) / bb_range if bb_range > 0 else 0.5

        sma_20 = float(close.tail(20).mean())
        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else sma_20

        # Trend semaine (5 jours ouvrés)
        week_close = close.tail(10)
        if len(week_close) >= 2:
            week_change = (week_close.iloc[-1] - week_close.iloc[0]) / week_close.iloc[0]
            trend_1w = "UP" if week_change > 0.01 else ("DOWN" if week_change < -0.01 else "FLAT")
        else:
            trend_1w = "FLAT"

        # ── Signal composite ──
        signal, score, breakdown = _compute_signal(rsi, macd_hist, volume_ratio, bb_position, trend_1w)

        result = {
            "ticker": ticker,
            "name": TICKER_NAMES.get(ticker, ticker),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 3),
            "volume": current_volume,
            "volume_avg_20d": avg_volume,
            "volume_ratio": round(volume_ratio, 2),
            "currency": "EUR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_open": True,
            "indicators": {
                "rsi_14": round(rsi, 1),
                "macd": round(macd_val, 3),
                "macd_signal": round(macd_sig, 3),
                "macd_hist": round(macd_hist, 3),
                "bb_upper": round(bb_upper, 2),
                "bb_middle": round(bb_middle, 2),
                "bb_lower": round(bb_lower, 2),
                "bb_position": round(bb_position, 3),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "trend_1w": trend_1w,
            },
            "signal": signal,
            "score": score,
            "score_breakdown": breakdown,
        }

        # Mise en cache Redis
        await cache_set(f"quote:{ticker}", result, ttl=settings.REDIS_CACHE_TTL_QUOTES)
        await cache_set(f"signal:{ticker}", {
            "ticker": ticker,
            "signal": signal,
            "score": score,
            "indicators": result["indicators"],
            "score_breakdown": breakdown,
            "timestamp": result["timestamp"],
        }, ttl=settings.REDIS_CACHE_TTL_SIGNALS)

        return result

    except Exception as e:
        logger.error(f"Erreur fetch_ticker_data({ticker}): {e}")
        return None


async def fetch_indices() -> list[dict]:
    """Récupère les cours des indices de référence (CAC40, etc.)."""
    import json, os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tickers.json")
    with open(path) as f:
        data = json.load(f)

    indices = []
    for idx in data.get("indices_reference", []):
        ticker = idx["ticker"]
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                lambda t=ticker: yf.Ticker(t).fast_info
            )
            if info:
                last = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)
                if last and prev:
                    chg = last - prev
                    chg_pct = chg / prev * 100
                    indices.append({
                        "ticker": ticker,
                        "name": idx["name"],
                        "price": round(last, 2),
                        "change": round(chg, 2),
                        "change_pct": round(chg_pct, 3),
                    })
        except Exception as e:
            logger.warning(f"Erreur indice {ticker}: {e}")

    return indices


async def collect_all() -> dict:
    """
    Collecte tous les tickers en parallèle (batches de 10).
    Retourne un dict {ticker: data}.
    """
    all_results = {}
    batch_size = 10

    for i in range(0, len(TICKERS), batch_size):
        batch = TICKERS[i: i + batch_size]
        tasks = [fetch_ticker_data(t["ticker"]) for t in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for t, res in zip(batch, results):
            if isinstance(res, dict):
                all_results[t["ticker"]] = res
            elif isinstance(res, Exception):
                logger.error(f"Exception pour {t['ticker']}: {res}")

        # Petit délai entre batches pour éviter rate limit
        if i + batch_size < len(TICKERS):
            await asyncio.sleep(0.5)

    logger.info(f"Collecte terminée : {len(all_results)}/{len(TICKERS)} tickers OK")
    return all_results
