"""
cache/redis_client.py — Client Redis async + cache mémoire local (toujours actif).
Compatible redis-py 5.x (sans ssl_cert_reqs, incompatible avec Upstash sinon).
"""
import json
import ssl
import time
from typing import Any, Optional
from urllib.parse import urlparse
import redis.asyncio as aioredis
from loguru import logger
from backend.config import settings


_redis: Optional[aioredis.Redis] = None
_redis_ok: bool = False
_redis_last_error: Optional[str] = None
_skip_pubsub: bool = False
_memory: dict[str, tuple[Any, float]] = {}


def _normalize_redis_url(url: str) -> str:
    url = (url or "").strip().strip('"').strip("'")
    if url.upper().startswith("REDIS_URL="):
        url = url.split("=", 1)[1].strip().strip('"').strip("'")
    return url


def _memory_set(key: str, value: Any, ttl: int) -> None:
    _memory[key] = (value, time.time() + ttl)


def _memory_get(key: str) -> Optional[Any]:
    entry = _memory.get(key)
    if not entry:
        return None
    value, expires = entry
    if time.time() > expires:
        del _memory[key]
        return None
    return value


def _redis_url_hint() -> dict:
    url = _normalize_redis_url(settings.REDIS_URL or "")
    if not url:
        return {"configured": False, "scheme": None, "host": None}
    parsed = urlparse(url)
    return {
        "configured": True,
        "scheme": parsed.scheme,
        "host": parsed.hostname,
    }


async def _connect_redis() -> aioredis.Redis:
    """Connexion Upstash — redis-py 5.x (pas de ssl_cert_reqs)."""
    url = _normalize_redis_url(settings.REDIS_URL or "")
    if not url:
        raise ConnectionError("REDIS_URL vide")
    if url.startswith("https://"):
        raise ConnectionError("URL REST https:// — utiliser rediss:// (onglet TCP Upstash)")

    errors: list[str] = []

    # Méthode 1 : from_url simple (rediss:// gère TLS automatiquement)
    try:
        client = await aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception as e:
        errors.append(f"from_url: {e}")

    # Méthode 2 : contexte SSL explicite (redis-py 5)
    if url.startswith("rediss://"):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            client = await aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                ssl=ctx,
            )
            await client.ping()
            return client
        except Exception as e:
            errors.append(f"ssl_context: {e}")

    raise ConnectionError(" | ".join(errors))


async def get_redis() -> aioredis.Redis:
    global _redis, _redis_ok, _redis_last_error
    if _redis is None:
        _redis = await _connect_redis()
        _redis_ok = True
        _redis_last_error = None
        logger.info("Redis connecté")
    return _redis


async def cache_set(key: str, value: Any, ttl: int = 60) -> bool:
    _memory_set(key, value, ttl)
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
        _redis_ok = True
        _redis_last_error = None
    except Exception as e:
        _redis_last_error = str(e)
        logger.debug(f"Redis SET [{key}]: {e}")
    return True


async def cache_get(key: str) -> Optional[Any]:
    mem = _memory_get(key)
    if mem is not None:
        return mem
    try:
        r = await get_redis()
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception as e:
        logger.debug(f"Redis GET [{key}]: {e}")
        return None


async def cache_delete(key: str) -> bool:
    _memory.pop(key, None)
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception:
        pass
    return True


async def publish(channel: str, message: Any) -> bool:
    if _skip_pubsub or not _redis_ok:
        return False
    try:
        r = await get_redis()
        await r.publish(channel, json.dumps(message, default=str))
        return True
    except Exception as e:
        logger.debug(f"Redis PUBLISH: {e}")
        return False


def _quotes_from_memory() -> dict:
    result = {}
    for key, (val, expires) in list(_memory.items()):
        if not key.startswith("quote:"):
            continue
        if time.time() > expires:
            del _memory[key]
            continue
        result[key.replace("quote:", "")] = val
    return result


def _signals_from_memory() -> dict:
    result = {}
    for key, (val, expires) in list(_memory.items()):
        if not key.startswith("signal:"):
            continue
        if time.time() > expires:
            del _memory[key]
            continue
        result[key.replace("signal:", "")] = val
    return result


async def get_all_quotes() -> dict:
    result = _quotes_from_memory()
    if not _redis_ok:
        return result
    try:
        r = await get_redis()
        keys = await r.keys("quote:*")
        if keys:
            values = await r.mget(keys)
            for key, val in zip(keys, values):
                if val:
                    ticker = key.replace("quote:", "")
                    result[ticker] = json.loads(val)
    except Exception as e:
        logger.debug(f"Redis get_all_quotes: {e}")
    return result


async def get_all_signals() -> dict:
    result = _signals_from_memory()
    if not _redis_ok:
        return result
    try:
        r = await get_redis()
        keys = await r.keys("signal:*")
        if keys:
            values = await r.mget(keys)
            for key, val in zip(keys, values):
                if val:
                    ticker = key.replace("signal:", "")
                    result[ticker] = json.loads(val)
    except Exception as e:
        logger.debug(f"Redis get_all_signals: {e}")
    return result


def get_redis_diagnostic() -> dict:
    hint = _redis_url_hint()
    return {
        **hint,
        "last_error": _redis_last_error,
        "redis_ok": _redis_ok,
        "pubsub_paused": _skip_pubsub,
        "memory_keys": len(_memory),
        "memory_quotes": len(_quotes_from_memory()),
    }


async def redis_ping() -> bool:
    global _redis_ok, _redis, _redis_last_error
    url = _normalize_redis_url(settings.REDIS_URL or "")
    if not url:
        _redis_last_error = "REDIS_URL non définie"
        return False
    if url.startswith("https://"):
        _redis_last_error = "Mauvaise URL REST https://"
        return False
    try:
        if _redis is None:
            _redis = await _connect_redis()
        else:
            await _redis.ping()
        _redis_ok = True
        _redis_last_error = None
        return True
    except Exception as e:
        _redis_last_error = str(e)
        _redis_ok = False
        if _redis:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None
        return False


def disable_redis_pubsub() -> None:
    """Pause le listener pub/sub (évite le spam de logs si Redis HS)."""
    global _skip_pubsub
    _skip_pubsub = True


def enable_redis_pubsub() -> None:
    global _skip_pubsub
    _skip_pubsub = False


async def close_redis():
    global _redis, _redis_ok
    if _redis:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
    _redis_ok = False
