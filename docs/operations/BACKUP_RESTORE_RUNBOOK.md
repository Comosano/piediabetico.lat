# 🛡️ RUNBOOK OPERATIVO: BACKUP, INTEGRIDAD Y RESTAURACIÓN (DISASTER RECOVERY)
### *Plataforma:* **piediabetico.lat** — VPS Producción  
### *Motor Principal:* **Restic + Cloudflare R2 Standard (S3-Compatible)**
### *Clasificación:* **P0 Operacional / Continuidad del Negocio**

---

## 1. 🎯 OBJETIVO Y ARQUITECTURA GENERAL

Este documento describe el procedimiento operativo estándar para:
1. Generar copias de respaldo consistentes, deduplicadas y cifradas hacia **Cloudflare R2 Standard** a costo operativo **USD $0**.
2. Utilizar **`restic`** como motor único para cifrado cliente (AES-256-GCM / Poly1305), snapshots, integridad (`restic check`), retención y restauración.
3. Reconstruir un servidor/VPS completo desde cero ante un incidente catastrófico (*Disaster Recovery*).
4. Restaurar la base de datos PostgreSQL, los objetos en MinIO y validar la continuidad operativa del sistema con medición de RTO (*Recovery Time Objective*).

> [!IMPORTANT]
> **REGLAS DE ORO DE SEGURIDAD Y PRIVACIDAD:**
> - **Cero texto plano fuera del VPS:** Todo dato clínico, archivo de configuración o base de datos que abandone el servidor viaja cifrado por Restic antes de transmitirse.
> - **Cero copias en caliente:** Nunca respaldar copiando directamente los directorios físicos de PostgreSQL (`/var/lib/postgresql/data`) ni de MinIO (`/data`). Usar siempre `pg_dump --format=custom` y la API S3/MinIO Client (`mc mirror`).
> - **Cero secretos en repositorios o logs:** La contraseña de Restic (`RESTIC_PASSWORD`) y las credenciales de Cloudflare R2 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) residen exclusivamente en variables de entorno seguras fuera de Git.

---

## 2. 🗂️ CLASIFICACIÓN DE COMPONENTES DEL SISTEMA

| Componente | Clasificación | Justificación y Estrategia de Respaldo |
| :--- | :--- | :--- |
| **PostgreSQL** (`piediadbetico`) | **`MUST_BACKUP`** | Base de datos transaccional con historias clínicas, usuarios, pacientes, heridas, consentimientos y relaciones de cuidado. Respaldo vía `pg_dump` (`--format=custom`). |
| **MinIO** (`piediabetico-media`) | **`MUST_BACKUP`** | Almacenamiento S3 de fotografías clínicas originales, fotos procesadas desidentificadas, máscaras U-Net y reportes generados. Respaldo exportado vía S3 API / MinIO Client hacia snapshot Restic. |
| **Configuración Crítica** (`.env`, Nginx, Alembic) | **`MUST_BACKUP`** | Parámetros de entorno, llaves de API, claves JWT y configuración proxy. Respaldo incluido exclusivamente dentro del snapshot cifrado de Restic. |
| **Redis** (Cache / Broker) | **`REGENERABLE`** | Memoria volátil para sesiones y colas de tareas. Se reconstruye automáticamente al arrancar. |
| **Imágenes Docker** | **`REGENERABLE`** | Se reconstruyen a partir de los `Dockerfile` y `docker-compose.prod.yml` del repositorio GitHub. |
| **Modelos de IA** (`.onnx`, `.keras`) | **`REGENERABLE`** | Pesos reproducibles almacenados en el repositorio / Git LFS / storage de modelos. |
| **Dependencias Python / Node.js** | **`REGENERABLE`** | Se instalan mediante `pip install -r requirements_backend.txt` y `npm install`. |

---

## 3. 🚀 PROCEDIMIENTO DE BACKUP RESTIC + CLOUDFLARE R2

Los scripts operan en `backend/scripts/backup/`.

### A. Configuración de Variables de Entorno en el VPS
```bash
# Variables para Restic y Cloudflare R2 Standard (S3-compatible)
export RESTIC_REPOSITORY="s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<BUCKET_NAME>"
export RESTIC_PASSWORD="<CLAVE_MAESTRA_RESTIC_FUERA_DE_GIT>"
export AWS_ACCESS_KEY_ID="<R2_ACCESS_KEY_ID>"
export AWS_SECRET_ACCESS_KEY="<R2_SECRET_ACCESS_KEY>"
```

### B. Ejecución del Backup Completo
```bash
# Ejecutar staging, dump consistente, export S3 y snapshot Restic
bash backend/scripts/backup/backup_restic.sh
```

* **Flujo Interno:**
  1. Valida presencia de credenciales (sin imprimir valores).
  2. Genera `pg_dump --format=custom --compress=9` en directorio staging temporal seguro.
  3. Exporta objetos y metadatos de MinIO vía API S3 a staging.
  4. Empaqueta `.env`, `nginx_piediabetico.conf`, `docker-compose.prod.yml` y migraciones Alembic.
  5. Restic cifra con AES-256-GCM y sube el snapshot deduplicado a Cloudflare R2.
  6. Purga segura del staging temporal (`rm -rf /tmp/staging`).
  7. Ejecuta `restic check --read-data-subset=10%`.

---

## 4. 🔍 VERIFICACIÓN DE INTEGRIDAD Y RETENCIÓN

```bash
# Verificar snapshots y árbol de datos
bash backend/scripts/backup/verify_restic.sh
```

### Política de Retención Configurada:
* **7 Diarios:** Un snapshot por cada uno de los últimos 7 días.
* **4 Semanales:** Un snapshot al final de cada una de las últimas 4 semanas.
* **3 Mensuales:** Un snapshot al final de cada uno de los últimos 3 meses.

```bash
# Aplicar política de retención en Cloudflare R2 (tras verificación del primer restore)
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune
```

---

## 5. 🚨 PROCEDIMIENTO DE RECONSTRUCCIÓN DESDE CERO (DISASTER RECOVERY)

Si el servidor VPS queda completamente destruido o se migra a un nuevo host:

### Paso 1: Aprovisionar nuevo VPS y dependencias base
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose git restic curl
sudo systemctl enable --now docker
```

### Paso 2: Clonar el repositorio desde GitHub
```bash
git clone https://github.com/Comosano/piediabetico.lat.git /opt/piediabetico
cd /opt/piediabetico
```

### Paso 3: Configurar variables de recuperación
```bash
export RESTIC_REPOSITORY="s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<BUCKET_NAME>"
export RESTIC_PASSWORD="<CLAVE_MAESTRA_RESTIC_FUERA_DE_GIT>"
export AWS_ACCESS_KEY_ID="<R2_ACCESS_KEY_ID>"
export AWS_SECRET_ACCESS_KEY="<R2_SECRET_ACCESS_KEY>"
```

### Paso 4: Iniciar infraestructura Docker mínima
```bash
cd /opt/piediabetico/backend
docker compose -f docker-compose.prod.yml up -d postgres minio redis
```

### Paso 5: Ejecutar script de Restauración Total
```bash
bash scripts/backup/restore_restic.sh latest
```
* Descarga el snapshot desde Cloudflare R2.
* Restaura la base de datos PostgreSQL (`pg_restore --clean --if-exists`).
* Restaura los objetos y fotos clínicas en MinIO.
* Restaura las configuraciones críticas (`.env`, Nginx).
* Mide y reporta el **RTO real**.

### Paso 6: Iniciar el stack completo y verificar
```bash
docker compose -f docker-compose.prod.yml up -d api
```

---

## 6. ✅ VERIFICACIÓN POST-RESTAURACIÓN (*SMOKE TEST CHECKLIST*)

1. **Healthcheck API:**
   ```bash
   curl -s http://127.0.0.1:8000/health
   # Debe responder: {"status":"ok"}
   ```
2. **Conteo de Tablas y Registros en PostgreSQL:**
   Verificar que existan registros en:
   * `organizations`
   * `users`
   * `patients`
   * `wounds`
   * `wound_evaluations`
   * `wound_images`
   * `patient_consents`
   * `care_relationships`
3. **Muestra de Objetos en MinIO:**
   Verificar que los hashes SHA-256 de las fotografías restauradas coincidan bit-a-bit con los registrados en base de datos (`wound_images.file_hash_sha256`).
4. **Calculadoras Públicas:**
   Verificar que `/agentes/san-elian` y `/agentes/iwgdf` respondan con código `200`.
