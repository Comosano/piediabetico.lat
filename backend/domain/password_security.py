"""
╔══════════════════════════════════════════════════════════════════════╗
║  PASSWORD_SECURITY.PY — piediabetico.lat                             ║
║  Módulo Criptográfico de Almacenamiento y Verificación de Passwords  ║
║  Estándar OWASP / Argon2id + PBKDF2-SHA256                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import hmac
import hashlib
import secrets
import logging
from typing import Optional

logger = logging.getLogger("password_security")

# Intentar inicializar Argon2id (Recomendado por OWASP)
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
    _ARGON2_AVAILABLE = True
    _ph = PasswordHasher(
        time_cost=3,        # 3 iteraciones
        memory_cost=65536,  # 64 MB
        parallelism=4,      # 4 hilos
        hash_len=32,
        salt_len=16
    )
except ImportError:
    _ARGON2_AVAILABLE = False
    _ph = None


def hash_password(raw_password: str) -> str:
    """
    Genera un hash seguro y salado para la contraseña en texto plano.
    Utiliza Argon2id si está disponible; de lo contrario utiliza PBKDF2-HMAC-SHA256 (600.000 iteraciones).
    NUNCA almacena ni loguea la contraseña en texto plano.
    """
    if not raw_password or not isinstance(raw_password, str):
        raise ValueError("La contraseña debe ser una cadena no vacía.")

    if _ARGON2_AVAILABLE and _ph is not None:
        return _ph.hash(raw_password)

    # Fallback PBKDF2-HMAC-SHA256
    salt = secrets.token_hex(16)
    iterations = 600000
    derived = hashlib.pbkdf2_hmac(
        'sha256',
        raw_password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def verify_password(raw_password: str, password_hash: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash almacenado.
    Soporta hashes Argon2id y PBKDF2-HMAC-SHA256 con comparación en tiempo constante.
    Retorna True si coincide, False en caso contrario.
    NUNCA lanza excepciones no controladas ni expone detalles del error en logs.
    """
    if not raw_password or not password_hash:
        return False

    if not isinstance(raw_password, str) or not isinstance(password_hash, str):
        return False

    # 1. Verificación Argon2id
    if password_hash.startswith("$argon2"):
        if _ARGON2_AVAILABLE and _ph is not None:
            try:
                return _ph.verify(password_hash, raw_password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False
            except Exception:
                return False
        else:
            logger.warning("Hash Argon2 detectado pero librería argon2 no está disponible en este entorno.")
            return False

    # 2. Verificación PBKDF2-HMAC-SHA256
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            parts = password_hash.split("$")
            if len(parts) != 4:
                return False
            _, iterations_str, salt, stored_hash = parts
            iterations = int(iterations_str)
            derived = hashlib.pbkdf2_hmac(
                'sha256',
                raw_password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            )
            return hmac.compare_digest(derived.hex(), stored_hash)
        except Exception:
            return False

    return False
