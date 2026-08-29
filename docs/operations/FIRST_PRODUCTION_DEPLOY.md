# 🚀 GUÍA DE PRIMER DESPLIEGUE EN PRODUCCIÓN (FIRST DEPLOY)
### *Plataforma:* **piediabetico.lat** — VPS Linux Producción  
### *Fecha de Elaboración:* 29 de Agosto de 2026

---

## 1. 📋 PRE-REQUISITOS DEL SERVIDOR

* **Sistema Operativo:** Ubuntu 22.04 LTS, Ubuntu 24.04 LTS o Debian 12 limpio.
* **Recursos Mínimos Recomendados:** 2–4 vCPU, 4–8 GB RAM, 50–80 GB SSD NVMe.
* **Acceso:** Acceso root o usuario con privilegios `sudo` vía SSH.
* **Puertos de Red Abiertos:**
  * `22/tcp` (SSH de administración)
  * `80/tcp` (HTTP - Nginx / Certbot)
  * `443/tcp` (HTTPS - Nginx)
* **Puertos Protegidos (Cero acceso externo directo):** `5432` (PostgreSQL), `6379` (Redis), `8000` (FastAPI), `9000/9001` (MinIO).

---

## 2. ⚡ PASO A PASO: INSTALACIÓN DESDE UN SERVIDOR VACÍO

```
Servidor Linux Vacío ──> Git Clone ──> Setup Server ──> .env ──> Deploy ──> Alembic ──> Healthcheck
```

### Paso 1: Conectar al VPS por SSH
```bash
ssh root@<IP_DEL_SERVIDOR>
```

### Paso 2: Clonar el Repositorio
```bash
git clone https://github.com/Comosano/piediabetico.lat.git /opt/piediabetico
cd /opt/piediabetico
```

### Paso 3: Ejecutar el Bootstrap Inicial
```bash
# Instala Docker, Docker Compose, UFW firewall, Fail2ban, Restic y crea directorios
bash deploy/setup_server.sh
```

### Paso 4: Configurar los Secretos de Producción (.env)
```bash
# Copiar plantilla de variables de entorno
cp .env.example .env
cp .env.example backend/.env

# Editar y completar las credenciales reales
nano .env
```
> [!IMPORTANT]
> **Checklist de Parámetros Obligatorios a Configurar en `.env`:**
> - [ ] `ENVIRONMENT=production`
> - [ ] `SECRET_KEY` (Generar una cadena aleatoria de 64 caracteres)
> - [ ] `ADMIN_API_KEY` (Generar clave aleatoria para triggers internos)
> - [ ] `POSTGRES_PASSWORD` (Contraseña robusta para base de datos)
> - [ ] `MINIO_ROOT_PASSWORD` (Contraseña robusta para Object Storage)
> - [ ] `ALLOWED_ORIGINS=https://piediabetico.lat,https://app.piediabetico.lat,https://api.piediabetico.lat`
> - [ ] Claves de API de proveedores de IA (`NVIDIA_NIM_API_KEY`, `DASHSCOPE_API_KEY`, etc.)
> - [ ] Credenciales de Restic / Cloudflare R2 (`RESTIC_REPOSITORY`, `RESTIC_PASSWORD`, etc.)

### Paso 5: Desplegar el Stack de Servicios y Migraciones
```bash
# Inicia contenedores Docker, ejecuta migraciones Alembic y valida /health
bash deploy/deploy.sh
```

### Paso 6: Configurar el Servidor Web Nginx
```bash
# Instalar Nginx en el host
apt-get install -y nginx certbot python3-certbot-nginx

# Copiar la configuración del proxy inverso
cp deploy/nginx_production.conf /etc/nginx/sites-available/piediabetico
ln -sf /etc/nginx/sites-available/piediabetico /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Probar sintaxis y recargar
nginx -t && systemctl reload nginx
```

### Paso 7: Obtener Certificados SSL/TLS (Let's Encrypt / Cloudflare Origin CA)
```bash
# Una vez apuntados los registros DNS:
certbot --nginx -d piediabetico.lat -d www.piediabetico.lat -d app.piediabetico.lat -d api.piediabetico.lat
```

---

## 3. ✅ VALIDACIÓN POST-DESPLIEGUE (*SMOKE TEST*)

Ejecutar las siguientes pruebas en el servidor para certificar el estado operativo:

```bash
# 1. Healthcheck minimalista del backend
curl -s http://127.0.0.1:8000/health
# Respuesta esperada: {"status":"ok"}

# 2. Verificar que la documentación pública esté bloqueada en producción
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
# Respuesta esperada: 404

# 3. Verificar estado de migraciones Alembic
docker compose -f backend/docker-compose.prod.yml exec -T api alembic current
# Respuesta esperada: 003_care_relationships (head)

# 4. Verificar aislamiento de puertos (no deben responder desde afuera)
# Intentar conectar a 5432 o 6379 desde máquina externa -> Conexión rechazada por UFW
```

---

## 4. 🔄 MANTENIMIENTO Y COMANDOS DE RUTINA

```bash
# Ver logs en tiempo real de la API
docker compose -f backend/docker-compose.prod.yml logs -f api

# Ver logs de tareas Celery
docker compose -f backend/docker-compose.prod.yml logs -f celery_worker

# Reiniciar todos los servicios
docker compose -f backend/docker-compose.prod.yml restart

# Ejecutar backup manual inmediato hacia Cloudflare R2
bash backend/scripts/backup/backup_restic.sh
```
