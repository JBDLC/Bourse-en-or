"""
models/schemas.py — Modèles Pydantic pour toute l'application
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ── Quote (cours temps réel) ──────────────────────────────────────────────────

class Quote(BaseModel):
    ticker: str
    name: str
    price: float
    change: float                    # variation absolue
    change_pct: float                # variation en %
    volume: int
    volume_avg_20d: Optional[int] = None
    volume_ratio: Optional[float] = None  # volume / moyenne
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    market_cap: Optional[float] = None
    currency: str = "EUR"
    exchange: str = ""
    timestamp: datetime
    is_open: bool = True             # marché ouvert ?


# ── Indicateurs techniques ────────────────────────────────────────────────────

class TechnicalIndicators(BaseModel):
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_position: Optional[float] = None  # 0=bas bande, 1=haut bande
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    trend_1d: Optional[Literal["UP", "DOWN", "FLAT"]] = None
    trend_1w: Optional[Literal["UP", "DOWN", "FLAT"]] = None


# ── Signal ────────────────────────────────────────────────────────────────────

SignalType = Literal["STRONG_BUY", "BUY", "NEUTRAL", "AVOID", "STRONG_AVOID"]

class Signal(BaseModel):
    ticker: str
    signal: SignalType
    score: int = Field(ge=0, le=100)
    indicators: TechnicalIndicators
    score_breakdown: dict = {}       # détail pondération
    timestamp: datetime


# ── Analyse IA ────────────────────────────────────────────────────────────────

class AIAnalysis(BaseModel):
    ticker: str
    signal: Literal["BUY", "HOLD", "AVOID"]
    score: int = Field(ge=0, le=100)
    cause: str                       # cause du mouvement
    opportunity: str                 # opportunité court terme
    risk: str                        # principal risque
    horizon: Literal["1j", "2j", "3j"]
    ai_analyzed: bool = True
    timestamp: datetime


# ── Recommandation complète ───────────────────────────────────────────────────

class Recommendation(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float
    signal: SignalType
    score: int
    cause: Optional[str] = None
    opportunity: Optional[str] = None
    risk: Optional[str] = None
    horizon: Optional[str] = None
    ai_analyzed: bool = False
    indicators: Optional[TechnicalIndicators] = None
    timestamp: datetime


# ── News ─────────────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    ticker: str
    headline: str
    summary: Optional[str] = None
    source: str
    url: str
    sentiment: Optional[Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]] = None
    sentiment_score: Optional[float] = None  # -1 à 1
    published_at: datetime


# ── Watchlist ────────────────────────────────────────────────────────────────

class WatchlistItem(BaseModel):
    ticker: str
    name: str
    added_at: datetime
    alert_above: Optional[float] = None
    alert_below: Optional[float] = None
    notes: Optional[str] = None


class WatchlistAdd(BaseModel):
    ticker: str
    alert_above: Optional[float] = None
    alert_below: Optional[float] = None
    notes: Optional[str] = None


# ── Alerte ───────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    id: int
    ticker: str
    name: str
    alert_type: Literal["PRICE_ABOVE", "PRICE_BELOW", "SIGNAL_CHANGE"]
    threshold: Optional[float] = None
    current_value: float
    message: str
    triggered_at: datetime
    acknowledged: bool = False


# ── WebSocket messages ────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: Literal["quote_update", "signal_update", "alert", "ping"]
    timestamp: datetime
    data: dict


# ── Réponses API ──────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    timestamp: datetime


class QuotesResponse(BaseModel):
    quotes: list[Quote]
    count: int
    last_update: datetime
    market_open: bool


class SignalsResponse(BaseModel):
    signals: list[Signal]
    count: int
    last_update: datetime


class RecommendationsResponse(BaseModel):
    recommendations: list[Recommendation]
    count: int
    top_buy: Optional[Recommendation] = None
    last_update: datetime
    ai_analyses_count: int
