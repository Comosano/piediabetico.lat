"""
╔══════════════════════════════════════════════════════════════════════╗
║  SESSION_STORE.PY — piediabetico.lat                                 ║
║  Gestor de Sesiones Multi-Worker en Redis con Hashes SHA-256         ║
║  Zero Raw Bearer Tokens en Storage · TTL 24h · Fail-Closed Estricto  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import secrets
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger("session_store")

# Excepción explícita para caída de Redis (Fail-Closed)
class RedisSessionUnavailableError(Exception):
    """Lanzada cuando Redis no responde o la conexión falla, forzando Fail-Closed."""
    pass


_redis_pool = None

def get_redis_url() -> str:
    """Obtiene la URL de Redis desde variables de entorno."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_client():
    """Retorna un cliente Redis conectado con pool y timeouts configurados."""
    global _redis_pool
    try:
        import redis
        if _redis_pool is None:
            _redis_pool = redis.ConnectionPool.from_url(
                get_redis_url(),
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                max_connections=20
            )
        return redis.Redis(connection_pool=_redis_pool)
    except Exception as e:
        logger.error(f"Error inicializando conexión a Redis: {e}")
        raise RedisSessionUnavailableError(f"No se pudo conectar a Redis: {e}")


def hash_session_token(raw_token: str) -> str:
    """
    Calcula el hash SHA-256 hexadecimal del token opaco.
    Garantiza que el Bearer Token en texto plano NUNCA se almacene en Redis.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValueError("El token de sesión debe ser una cadena no vacía.")
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def create_session(
    user_id: str,
    ttl_seconds: int = 86400,
    redis_client = None
) -> str:
    """
    Genera un token opaco seguro (pd_sess_<32 bytes urlsafe>), calcula su SHA-256,
    y persiste la metadata mínima (user_id, created_at) en Redis con expiración automática (TTL = 24h).
    Retorna el bearer token en texto plano para el cliente.
    """
    if not user_id:
        raise ValueError("user_id es obligatorio para crear una sesión.")

    raw_token = f"pd_sess_{secrets.token_urlsafe(32)}"
    token_hash = hash_session_token(raw_token)
    redis_key = f"pilot_session:{token_hash}"

    # Minimización estricta de datos (Privacy by Design): Solo user_id y timestamp
    session_data = {
        "user_id": str(user_id),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        r = redis_client if redis_client is not None else get_redis_client()
        r.set(redis_key, json.dumps(session_data), ex=ttl_seconds)
        return raw_token
    except Exception as e:
        logger.error(f"Fallo al registrar sesión en Redis (Fail-Closed): {e}")
        raise RedisSessionUnavailableError(f"Fallo crítico registrando sesión en Redis: {e}")


def get_session(raw_token: str, redis_client = None) -> Optional[Dict[str, Any]]:
    """
    Resuelve una sesión activa desde Redis mediante el SHA-256 del token provisto.
    Si el token no existe o expiró el TTL, retorna None.
    Si Redis está inaccesible, lanza RedisSessionUnavailableError (Fail-Closed).
    """
    if not raw_token or not isinstance(raw_token, str) or len(raw_token) < 16:
        return None

    try:
        token_hash = hash_session_token(raw_token)
        redis_key = f"pilot_session:{token_hash}"
        r = redis_client if redis_client is not None else get_redis_client()
        val = r.get(redis_key)
        if not val:
            return None
        return json.loads(val)
    except RedisSessionUnavailableError:
        raise
    except Exception as e:
        logger.error(f"Error consultando sesión en Redis (Fail-Closed): {e}")
        raise RedisSessionUnavailableError(f"Redis no disponible para resolver sesión: {e}")


def delete_session(raw_token: str, redis_client = None) -> bool:
    """Elimina una sesión activa de Redis al cerrar sesión."""
    if not raw_token or not isinstance(raw_token, str):
        return False
    try:
        token_hash = hash_session_token(raw_token)
        redis_key = f"pilot_session:{token_hash}"
        r = redis_client if redis_client is not None else get_redis_client()
        return bool(r.delete(redis_key))
    except Exception as e:
        logger.warning(f"Error al eliminar sesión en Redis: {e}")
        return False
