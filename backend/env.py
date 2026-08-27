"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALEMBIC ENV.PY — Configuración del entorno de migraciones          ║
║  piediabetico.lat                                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  Lee la URL de la base de datos desde la variable de entorno        ║
║  DATABASE_URL para no hardcodear contraseñas en el código.          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Importar los modelos para que Alembic los detecte ────────────────
# Alembic necesita ver los modelos para generar migraciones automáticas
# con --autogenerate
from models import Base  # importa todos los modelos de models.py

# ── Configuración de Alembic ─────────────────────────────────────────
config = context.config

# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos — para autogenerate
target_metadata = Base.metadata

# ── Leer la URL desde variable de entorno ────────────────────────────
def get_url() -> str:
    """
    Lee DATABASE_URL del entorno.
    Formato esperado:
        postgresql://adminpd:PASSWORD@postgres:5432/piediadbetico

    En Docker Compose, 'postgres' es el nombre del servicio.
    En desarrollo local, usar 'localhost' en lugar de 'postgres'.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback para desarrollo local
        user     = os.getenv("POSTGRES_USER", "adminpd")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host     = os.getenv("POSTGRES_HOST", "localhost")
        port     = os.getenv("POSTGRES_PORT", "5432")
        db       = os.getenv("POSTGRES_DB", "piediadbetico")
        url      = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return url


# ── Modo offline (genera SQL sin conectarse a la BD) ─────────────────
def run_migrations_offline() -> None:
    """
    Genera el SQL de las migraciones sin conectarse a la base de datos.
    Útil para revisar qué SQL se va a ejecutar antes de aplicarlo.

    Uso: alembic upgrade head --sql
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Opciones de comparación para autogenerate
        compare_type=True,           # detecta cambios de tipo de columna
        compare_server_default=True, # detecta cambios en valores por defecto
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Modo online (aplica las migraciones directamente) ─────────────────
def run_migrations_online() -> None:
    """
    Aplica las migraciones directamente a la base de datos.

    Uso normal: alembic upgrade head
    """
    # Sobreescribir la URL con la variable de entorno
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # sin pool — cada migración abre y cierra conexión
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Soporte para pgvector — ignorar índices de tipo ivfflat en autogenerate
            include_schemas=False,
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Ejecutar según el modo ────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
