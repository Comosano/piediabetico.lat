# 🛡️ RUNBOOK OPERATIVO: BACKUP, INTEGRIDAD Y RESTAURACIÓN (DISASTER RECOVERY)
### *Plataforma:* **piediabetico.lat** — VPS Producción  
### *Clasificación:* **P0 Operacional / Continuidad del Negocio**

---

## 1. 🎯 OBJETIVO Y ARQUITECTURA GENERAL

Este documento describe el procedimiento operativo estándar para:
1. Generar copias de respaldo consistentes y cifradas fuera del VPS a costo operativo **USD $0**.
2. Verificar criptográficamente la integridad y no corrupción de los datos respaldados.
3. Reconstruir un servidor/VPS completo desde cero ante un incidente catastrófico (*Disaster Recovery*).
4. Restaurar la base de datos PostgreSQL, los objetos en MinIO y validar la continuidad operativa del sistema.

> [!IMPORTANT]
> **REGLAS DE ORO DE SEGURIDAD Y PRIVACIDAD:**
> - **Cero texto plano fuera del VPS:** Todo dato clínico, archivo de configuración o base de datos que abandone el servidor debe estar cifrado en el cliente (*Client-Side Encryption*) mediante AES-256-GCM o Poly1305.
> - **Cero copias en caliente:** Nunca respaldar copiando directamente los directorios físicos de PostgreSQL (`/var/lib/postgresql/data`) mientras el motor está activo. Usar siempre `pg_dump` consistente.
> - **Cero secretos en repositorios o logs:** Nunca imprimir ni registrar variables de entorno, claves maestras, contraseñas o datos identificables de pacientes (PII).

---

## 2. 🗂️ CLASIFICACIÓN DE COMPONENTES DEL SISTEMA

| Componente | Clasificación | Justificación y Estrategia de Respaldo |
| :--- | :--- | :--- |
| **PostgreSQL** (`piediadbetico`) | **`MUST_BACKUP`** | Base de datos transaccional con historias clínicas, usuarios, pacientes, heridas, consentimientos y relaciones de cuidado. Respaldo vía `pg_dump` (`--format=custom`). |
| **MinIO** (`piediabetico-media`) | **`MUST_BACKUP`** | Almacenamiento S3 de fotografías clínicas originales, fotos procesadas desidentificadas, máscaras U-Net y reportes generados. Respaldo de objetos vía S3 sync / Restic. |
| **Configuración Crítica** (`.env`, Nginx, Certs) | **`MUST_BACKUP`** | Parámetros de entorno, llaves de API, claves JWT y configuración proxy. Respaldo empaquetado y cifrado con `openssl` / `age`. |
| **Redis** (Cache / Broker) | **`REGENERABLE`** | Memoria volátil para sesiones y colas de tareas. Se reconstruye automáticamente al arrancar. |
| **Imágenes Docker** | **`REGENERABLE`** | Se reconstruyen a partir de los `Dockerfile` y `docker-compose.prod.yml` del repositorio GitHub. |
| **Modelos de IA** (`.onnx`, `.keras`) | **`REGENERABLE`** | Pesos reproducibles almacenados en el repositorio / Git LFS / storage de modelos. |
| **Dependencias Python / Node.js** | **`REGENERABLE`** | Se instalan mediante `pip install -r requirements_backend.txt` y `npm install`. |

---

## 3. 🚀 PROCEDIMIENTOS DE BACKUP MANUAL Y PROGRAMADO

Los scripts operan en `backend/scripts/backup/`.

### A. Respaldo de la Base de Datos PostgreSQL
```bash
# Ejecutar backup consistente de PostgreSQL
bash backend/scripts/backup/backup_database.sh
```
* **Salida esperada:** Genera un archivo `db_YYYYMMDD_HHMMSSZ.dump` en `/var/backups/piediabetico/db/`.
* **Mecanismo:** `pg_dump -U adminpd -d piediadbetico --format=custom --compress=9 --no-owner --clean`.

### B. Respaldo de Objetos MinIO
```bash
# Ejecutar backup de objetos y fotos clínicas
bash backend/scripts/backup/backup_objects.sh
```
* **Salida esperada:** Genera un archivo `objects_YYYYMMDD_HHMMSSZ.tar.gz` en `/var/backups/piediabetico/objects/`.

### C. Respaldo Cifrado de Configuración del Servidor
```bash
# Requiere la passphrase de cifrado en el entorno del operador
export BACKUP_PASSPHRASE="<CLAVE_MAESTRA_OPERACIONAL>"
bash backend/scripts/backup/backup_configuration.sh
```
* **Salida esperada:** Genera un archivo `config_YYYYMMDD_HHMMSSZ.tar.enc` cifrado con AES-256-CBC (PBKDF2 100.000 iteraciones).

---

## 4. 🔍 VERIFICACIÓN DE INTEGRIDAD

Antes de enviar el backup a cualquier destino externo, o de certificar un respaldo periódico, verificar su legibilidad y checksum:

```bash
# Verificar dump de base de datos
bash backend/scripts/backup/verify_backup.sh /var/backups/piediabetico/db/db_20260829_120000Z.dump

# Verificar archivo de objetos
bash backend/scripts/backup/verify_backup.sh /var/backups/piediabetico/objects/objects_20260829_120000Z.tar.gz
```
* **Validaciones ejecutadas:**
  * Archivo no vacío (> 100 bytes).
  * `pg_restore --list` verifica la integridad del catálogo de la base de datos sin alterar ninguna tabla.
  * `tar -tzf` verifica la descompresión sin corrupción de bloques.
  * Cálculo y registro del hash criptográfico **SHA-256**.

---

## 5. 🔄 POLÍTICA DE RETENCIÓN DE SNAPSHOTS

Se implementa una política de retención temporal *grandfather-father-son* configurable:
* **7 Diarios:** Un snapshot por cada uno de los últimos 7 días.
* **4 Semanales:** Un snapshot al final de cada una de las últimas 4 semanas.
* **3 Mensuales:** Un snapshot al final de cada uno de los últimos 3 meses.

---

## 6. 🚨 PROCEDIMIENTO DE RECONSTRUCCIÓN DESDE CERO (DISASTER RECOVERY)

Si el servidor VPS queda completamente destruido o inaccesible:

### Paso 1: Aprovisionar nuevo VPS y dependencias base
```bash
# En el nuevo servidor Linux (Debian 12 / Ubuntu 22.04 LTS):
sudo apt-get update && sudo apt-get install -y docker.io docker-compose git openssl curl
sudo systemctl enable --now docker
```

### Paso 2: Clonar el repositorio desde GitHub
```bash
git clone https://github.com/Comosano/piediabetico.lat.git /opt/piediabetico
cd /opt/piediabetico
```

### Paso 3: Descifrar la configuración crítica (.env)
```bash
# Descargar el archivo cifrado config_*.tar.enc desde el almacenamiento seguro externo
openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in config_20260829_120000Z.tar.enc \
    -out config_restored.tar \
    -pass pass:"<CLAVE_MAESTRA_OPERACIONAL>"

tar -xf config_restored.tar -C /opt/piediabetico/
rm -f config_restored.tar
```

### Paso 4: Levantar los servicios de infraestructura
```bash
cd /opt/piediabetico/backend
docker compose -f docker-compose.prod.yml up -d postgres minio redis
```

### Paso 5: Restaurar la Base de Datos PostgreSQL
```bash
# Ejecutar script de restauración sobre el contenedor postgres
bash scripts/backup/restore_database.sh /ruta/al/backup/db_20260829_120000Z.dump
```

### Paso 6: Restaurar los Objetos de MinIO
```bash
# Restaurar fotos clínicas y máscaras
bash scripts/backup/restore_objects.sh /ruta/al/backup/objects_20260829_120000Z.tar.gz
```

### Paso 7: Iniciar el stack completo y verificar
```bash
docker compose -f docker-compose.prod.yml up -d api
```

---

## 7. ✅ VERIFICACIÓN POST-RESTAURACIÓN (*SMOKE TEST CHECKLIST*)

Ejecutar las siguientes validaciones tras la restauración:
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
   Descargar un objeto de muestra y verificar que su hash SHA-256 coincida con el registrado en `wound_images.file_hash_sha256`.
4. **Calculadoras Públicas:**
   Verificar que `/agentes/san-elian` y `/agentes/iwgdf` respondan con código `200`.
