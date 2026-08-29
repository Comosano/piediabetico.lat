"""
╔══════════════════════════════════════════════════════════════════════╗
║  DATABASE.PY — piediabetico.lat                                      ║
║  Gestor de Conexión y Sesiones SQLAlchemy para PostgreSQL 16         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("database")

def get_database_url() -> str:
    """Obtiene la URL de conexión a PostgreSQL desde variables de entorno."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://adminpd:local_dev_password_pd_2026@localhost:5432/piediadbetico"
    )

_engine = None
_SessionLocal = None

def get_engine():
    """Retorna el motor SQLAlchemy singleton con pool_pre_ping."""
    global _engine
    if _engine is None:
        try:
            _engine = create_engine(
                get_database_url(),
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )
        except Exception as e:
            logger.warning(f"No se pudo inicializar engine SQLAlchemy: {e}")
            _engine = None
    return _engine

def get_sessionmaker():
    """Retorna la fábrica de sesiones de SQLAlchemy."""
    global _SessionLocal
    if _SessionLocal is None:
        eng = get_engine()
        if eng:
            _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        else:
            _SessionLocal = None
    return _SessionLocal

def get_db() -> Generator[Session, None, None]:
    """Generador de dependencias FastAPI para obtener una sesión de DB."""
    sm = get_sessionmaker()
    if sm is None:
        yield None
        return

    db = sm()
    try:
        yield db
    finally:
        db.close()
