"""
config.py — Paramètres centralisés de l'application
Toutes les variables d'environnement sont lues ici, nulle part ailleurs.
"""
import json
import os
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from typing import Any, List, Union


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Bourse en or"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development | production

    # ── API Keys ─────────────────────────────────────────────────
    # Optionnelle au démarrage : si absente, l'app tourne en mode "technique seul" (sans IA Claude)
    ANTHROPIC_API_KEY: str = ""
    TWELVE_DATA_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""

    # ── Base de données ───────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pea_trading"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_CACHE_TTL_QUOTES: int = 15       # secondes
    REDIS_CACHE_TTL_SIGNALS: int = 60      # secondes
    REDIS_CACHE_TTL_NEWS: int = 300        # 5 minutes

    # ── Collecte données ─────────────────────────────────────────
    REFRESH_INTERVAL_SECONDS: int = 15
    MAX_TICKERS: int = 60
    YFINANCE_PERIOD: str = "5d"            # période historique pour calculs
    YFINANCE_INTERVAL: str = "5m"          # granularité intraday

    # ── Signaux techniques ────────────────────────────────────────
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    VOLUME_MA_PERIOD: int = 20

    # Seuils signaux
    RSI_STRONG_BUY: float = 35.0
    RSI_BUY: float = 45.0
    RSI_AVOID: float = 65.0
    RSI_STRONG_AVOID: float = 75.0
    VOLUME_SPIKE_RATIO: float = 1.5

    # ── IA / Claude ───────────────────────────────────────────────
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 500
    CLAUDE_TIMEOUT: int = 30
    CLAUDE_RETRY_COUNT: int = 2
    AI_ANALYSIS_MIN_SCORE: int = 50        # score min pour déclencher analyse IA

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://pea-frontend.onrender.com",
    ]

    # ── Rate limiting ─────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100

    @model_validator(mode="before")
    @classmethod
    def redis_url_from_upstash(cls, data: Any) -> Any:
        """Accepte UPSTASH_REDIS_URL si REDIS_URL absent (copie depuis Upstash .env)."""
        if isinstance(data, dict):
            if not data.get("REDIS_URL") and data.get("UPSTASH_REDIS_URL"):
                data["REDIS_URL"] = data["UPSTASH_REDIS_URL"]
            elif not data.get("REDIS_URL"):
                env = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL", "")
                if env:
                    data["REDIS_URL"] = env
        return data

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def clean_redis_url(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip().strip('"').strip("'")
        # Erreur fréquente Render : coller toute la ligne REDIS_URL="rediss://..."
        if s.upper().startswith("REDIS_URL="):
            s = s.split("=", 1)[1].strip().strip('"').strip("'")
        return s

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Render env: '["https://xxx.onrender.com"]' -> liste Python pour CORS."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# ── Prompt système Claude ─────────────────────────────────────────────────────
CLAUDE_SYSTEM_PROMPT = """Tu es un analyste financier expert en trading court terme sur marchés européens.
Tu analyses des actions éligibles PEA France pour un investisseur particulier.
Tu prends en compte les indicateurs techniques ET les dernières actualités.
Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
Format strict :
{
  "signal": "BUY" | "HOLD" | "AVOID",
  "score": <entier 0-100>,
  "cause": "<1 phrase max 100 chars expliquant le mouvement récent>",
  "opportunity": "<1 phrase max 120 chars sur l'opportunité court terme>",
  "risk": "<1 phrase max 100 chars sur le principal risque>",
  "horizon": "1j" | "2j" | "3j"
}
Sois factuel, précis, jamais alarmiste. Horizon max 3 jours ouvrés.
Si les données sont insuffisantes, score = 50 et signal = HOLD."""
