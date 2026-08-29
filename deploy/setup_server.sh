#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SETUP_SERVER.SH — Bootstrap Idempotente para Ubuntu/Debian           ║
# ║  Plataforma: piediabetico.lat                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🦶 piediabetico.lat — Bootstrap de Servidor Producción Linux"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$(id -u)" -ne 0 ]; then
    echo "✗ Este script debe ejecutarse como root o con sudo."
    exit 1
fi

# ── 1. Actualización de Paquetes Base ──────────────────────────────────
echo "[1/6] Actualizando repositorios y paquetes del sistema..."
apt-get update -qq
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    restic \
    htop \
    jq

# ── 2. Instalación Idempotente de Docker & Docker Compose ──────────────
echo "[2/6] Verificando e instalando Docker Engine..."
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    echo "✓ Docker instalado y servicio activo."
else
    echo "✓ Docker ya se encuentra instalado."
fi

# ── 3. Configuración del Firewall UFW (Seguridad P0) ───────────────────
echo "[3/6] Configurando Firewall UFW (Solo puertos 22, 80 y 443)..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Nginx'
ufw allow 443/tcp comment 'HTTPS Nginx'
# Confirmar que 5432, 6379, 8000, 9000, 9001 no tengan reglas de entrada
ufw --force enable
echo "✓ Firewall UFW activo y bloqueando accesos directos no autorizados."

# ── 4. Estructura de Directorios y Volúmenes Persistentes ───────────────
echo "[4/6] Creando estructura de directorios y permisos..."
INSTALL_DIR="/opt/piediabetico"
mkdir -p \
    "${INSTALL_DIR}/data/postgres" \
    "${INSTALL_DIR}/data/minio" \
    "${INSTALL_DIR}/data/redis" \
    "${INSTALL_DIR}/data/workspace" \
    "${INSTALL_DIR}/modelos" \
    "/var/backups/piediabetico/db" \
    "/var/backups/piediabetico/objects" \
    "/var/backups/piediabetico/config" \
    "/var/www/piediabetico"

chmod 700 "${INSTALL_DIR}/data/postgres"
chmod 755 "${INSTALL_DIR}/data/minio"
chmod 755 "${INSTALL_DIR}/data/redis"
echo "✓ Directorios creados en ${INSTALL_DIR}."

# ── 5. Configuración de Fail2ban ───────────────────────────────────────
echo "[5/6] Configurando protección contra ataques de fuerza bruta (Fail2ban)..."
systemctl enable --now fail2ban

# ── 6. Resumen Final ───────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ BOOTSTRAP COMPLETADO EXITOSAMENTE"
echo "  Directorio de instalación: ${INSTALL_DIR}"
echo "  Siguiente paso: Clonar el repositorio y configurar el archivo .env"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
