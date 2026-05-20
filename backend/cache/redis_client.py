"""
cache/redis_client.py — Client Redis async avec helpers de cache
"""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
from loguru import logger
from backend.config import settings


_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Retourne l'instance Redis (singleton)."""
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def cache_set(key: str, value: Any, ttl: int = 60) -> bool:
    """Stocke une valeur JSON dans Redis avec TTL."""
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.error(f"Redis SET error [{key}]: {e}")
        return False


async def cache_get(key: str) -> Optional[Any]:
    """Récupère et désérialise une valeur JSON depuis Redis."""
    try:
        r = await get_redis()
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception as e:
        logger.error(f"Redis GET error [{key}]: {e}")
        return None


async def cache_delete(key: str) -> bool:
    """Supprime une clé Redis."""
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error [{key}]: {e}")
        return False


async def publish(channel: str, message: Any) -> bool:
    """Publie un message sur un channel Redis Pub/Sub."""
    try:
        r = await get_redis()
        await r.publish(channel, json.dumps(message, default=str))
        return True
    except Exception as e:
        logger.error(f"Redis PUBLISH error [{channel}]: {e}")
        return False


async def get_all_quotes() -> dict:
    """Récupère tous les cours depuis Redis (pattern: quote:*)."""
    try:
        r = await get_redis()
        keys = await r.keys("quote:*")
        if not keys:
            return {}
        values = await r.mget(keys)
        result = {}
        for key, val in zip(keys, values):
            if val:
                ticker = key.replace("quote:", "")
                result[ticker] = json.loads(val)
        return result
    except Exception as e:
        logger.error(f"Redis get_all_quotes error: {e}")
        return {}


async def get_all_signals() -> dict:
    """Récupère tous les signaux depuis Redis (pattern: signal:*)."""
    try:
        r = await get_redis()
        keys = await r.keys("signal:*")
        if not keys:
            return {}
        values = await r.mget(keys)
        result = {}
        for key, val in zip(keys, values):
            if val:
                ticker = key.replace("signal:", "")
                result[ticker] = json.loads(val)
        return result
    except Exception as e:
        logger.error(f"Redis get_all_signals error: {e}")
        return {}


async def redis_ping() -> bool:
    """Vérifie que Redis répond (diagnostic déploiement)."""
    try:
        r = await get_redis()
        return bool(await r.ping())
    except Exception as e:
        logger.error(f"Redis PING error: {e}")
        return False


async def close_redis():
    """Ferme la connexion Redis proprement."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
