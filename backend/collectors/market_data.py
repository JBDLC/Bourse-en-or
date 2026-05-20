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


def _min_bars_required() -> int:
    """Nombre minimum de bougies pour RSI/MACD."""
    return max(30, settings.MACD_SLOW + settings.MACD_SIGNAL + 5)


def _slice_ticker_from_batch(batch: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """Extrait le DataFrame d'un ticker depuis un téléchargement yfinance groupé."""
    if batch is None or batch.empty:
        return None
    if isinstance(batch.columns, pd.MultiIndex):
        level0 = batch.columns.get_level_values(0)
        if ticker in level0:
            return batch[ticker].dropna(how="all")
        level1 = batch.columns.get_level_values(1)
        if ticker in level1:
            return batch.xs(ticker, axis=1, level=1).dropna(how="all")
        return None
    return batch.dropna(how="all")


def _build_quote_from_df(ticker: str, df: pd.DataFrame) -> Optional[dict]:
    """Calcule cours + indicateurs à partir d'un historique OHLCV."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    close = df["Close"].dropna() if "Close" in df.columns else pd.Series(dtype=float)
    volume = df["Volume"].dropna() if "Volume" in df.columns else pd.Series(dtype=float)

    if len(close) < _min_bars_required():
        return None

    current_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else current_price
    change = current_price - prev_price
    change_pct = (change / prev_price * 100) if prev_price != 0 else 0

    current_volume = int(volume.iloc[-1]) if not volume.empty else 0
    avg_volume = int(volume.tail(20).mean()) if len(volume) >= 20 else current_volume
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

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

    week_close = close.tail(10)
    if len(week_close) >= 2:
        week_change = (week_close.iloc[-1] - week_close.iloc[0]) / week_close.iloc[0]
        trend_1w = "UP" if week_change > 0.01 else ("DOWN" if week_change < -0.01 else "FLAT")
    else:
        trend_1w = "FLAT"

    signal, score, breakdown = _compute_signal(rsi, macd_hist, volume_ratio, bb_position, trend_1w)

    return {
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


async def _cache_quote_result(result: dict) -> None:
    ticker = result["ticker"]
    await cache_set(f"quote:{ticker}", result, ttl=settings.REDIS_CACHE_TTL_QUOTES)
    await cache_set(
        f"signal:{ticker}",
        {
            "ticker": ticker,
            "signal": result["signal"],
            "score": result["score"],
            "indicators": result["indicators"],
            "score_breakdown": result.get("score_breakdown", {}),
            "timestamp": result["timestamp"],
        },
        ttl=settings.REDIS_CACHE_TTL_SIGNALS,
    )


def _yf_download_sync(tickers: list[str]) -> pd.DataFrame:
    """Téléchargement groupé (1 requête Yahoo) — plus fiable sur hébergeurs cloud."""
    if len(tickers) == 1:
        return yf.download(
            tickers[0],
            period=settings.YFINANCE_PERIOD,
            interval=settings.YFINANCE_INTERVAL,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    return yf.download(
        tickers,
        period=settings.YFINANCE_PERIOD,
        interval=settings.YFINANCE_INTERVAL,
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=False,
    )


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
        df = await loop.run_in_executor(None, lambda: _yf_download_sync([ticker]))
        ticker_df = _slice_ticker_from_batch(df, ticker) if df is not None else None
        if ticker_df is None and df is not None and not isinstance(df.columns, pd.MultiIndex):
            ticker_df = df

        result = _build_quote_from_df(ticker, ticker_df) if ticker_df is not None else None
        if not result:
            logger.warning(f"Données insuffisantes pour {ticker}")
            return None

        await _cache_quote_result(result)
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
    Collecte tous les tickers par lots yfinance groupés (moins de requêtes, plus fiable sur Render).
    Retourne un dict {ticker: data}.
    """
    all_results: dict = {}
    batch_size = 15
    loop = asyncio.get_event_loop()
    symbols = [t["ticker"] for t in TICKERS]

    for i in range(0, len(symbols), batch_size):
        chunk = symbols[i: i + batch_size]
        try:
            raw = await loop.run_in_executor(None, lambda c=chunk: _yf_download_sync(c))
        except Exception as e:
            logger.error(f"Erreur téléchargement batch {chunk[0]}..: {e}")
            await asyncio.sleep(1)
            continue

        for ticker in chunk:
            try:
                ticker_df = _slice_ticker_from_batch(raw, ticker)
                if ticker_df is None and len(chunk) == 1 and raw is not None:
                    ticker_df = raw
                result = _build_quote_from_df(ticker, ticker_df) if ticker_df is not None else None
                if result:
                    await _cache_quote_result(result)
                    all_results[ticker] = result
            except Exception as e:
                logger.error(f"Erreur traitement {ticker}: {e}")

        if i + batch_size < len(symbols):
            await asyncio.sleep(1)

    logger.info(f"Collecte terminée : {len(all_results)}/{len(TICKERS)} tickers OK")
    return all_results
