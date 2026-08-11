#!/bin/bash

# MATE — Script de backup automático
# Corre por cron todos los días a las 02:00
#
# Respalda:
#   1. MATE            → SQLite, ChromaDB, Neo4j, uploads, .env   (un solo .tar.gz)
#   2. cto_db          → contactos comerciales de CTO y AE        (pg_dump)
#   3. n8n             → flujos y credenciales de automatización  (pg_dump)
#   4. home-assistant  → config de dispositivos y Mosquitto       (tar)
#   5. OneDrive        → copia externa vía rclone
#
# Neo4j se detiene durante el tar: copiar sus archivos en caliente puede dejar
# un backup inconsistente. El trap garantiza que vuelva a levantar aunque el
# script falle a mitad de camino.

BACKUP_DIR="/home/jmontero/mate_backups"
AIDEN_DIR="/home/jmontero/aiden"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mate_backup_$DATE.tar.gz"
MAX_BACKUPS=7  # Mantener solo los últimos 7 de cada tipo

# Copia externa (rclone). Si el remote no existe, el script avisa y sigue.
RCLONE_REMOTE="onedrive"
RCLONE_PATH="0.0.3.Proyecto MATE/Backups"

mkdir -p "$BACKUP_DIR"
cd "$AIDEN_DIR" || { echo "[$DATE] ERROR: no existe $AIDEN_DIR"; exit 1; }

echo "[$DATE] ===== Iniciando backup ====="

# ── 1. MATE ───────────────────────────────────────────────────────────────────
echo "[$DATE] Deteniendo neo4j para copia consistente..."
docker compose stop neo4j >/dev/null 2>&1
trap 'docker compose start neo4j >/dev/null 2>&1' EXIT

tar -czf "$BACKUP_FILE" \
  -C "$AIDEN_DIR" \
  data/db \
  data/vectordb \
  data/neo4j \
  data/uploads \
  .env \
  2>/dev/null
TAR_RC=$?

docker compose start neo4j >/dev/null 2>&1
trap - EXIT
echo "[$DATE] neo4j levantado nuevamente."

if [ $TAR_RC -eq 0 ]; then
  echo "[$DATE] OK  MATE: $(du -sh "$BACKUP_FILE" | cut -f1) → $(basename "$BACKUP_FILE")"
else
  echo "[$DATE] ERROR: fallo el backup de MATE"
fi

# ── 2. Contactos comerciales (cto_db) ─────────────────────────────────────────
# Canal comercial de CTO y AE. pg_dump no requiere detener el servicio.
CTO_FILE="$BACKUP_DIR/cto_db_$DATE.sql.gz"
if docker ps --format '{{.Names}}' | grep -q '^cto-postgres$'; then
  if docker exec cto-postgres pg_dump -U postgres -d cto_db 2>/dev/null | gzip > "$CTO_FILE"; then
    echo "[$DATE] OK  cto_db: $(du -sh "$CTO_FILE" | cut -f1) → $(basename "$CTO_FILE")"
  else
    echo "[$DATE] ERROR: fallo el pg_dump de cto_db"
    rm -f "$CTO_FILE"
  fi
else
  echo "[$DATE] AVISO: cto-postgres no está corriendo, se omite"
fi

# ── 3. Flujos y credenciales de n8n ───────────────────────────────────────────
N8N_FILE="$BACKUP_DIR/n8n_$DATE.sql.gz"
if docker ps --format '{{.Names}}' | grep -q '^n8n-postgres$'; then
  if docker exec n8n-postgres pg_dump -U n8n -d n8n 2>/dev/null | gzip > "$N8N_FILE"; then
    echo "[$DATE] OK  n8n: $(du -sh "$N8N_FILE" | cut -f1) → $(basename "$N8N_FILE")"
  else
    echo "[$DATE] ERROR: fallo el pg_dump de n8n"
    rm -f "$N8N_FILE"
  fi
else
  echo "[$DATE] AVISO: n8n-postgres no está corriendo, se omite"
fi

# ── 4. Home Assistant + Mosquitto ─────────────────────────────────────────────
# Config de dispositivos y credenciales del broker MQTT.
#
# HA y Mosquitto crean sus archivos como root dentro del contenedor, así que un
# tar como jmontero falla justo en lo importante (.storage/auth, core.config,
# mosquitto/config/passwd). Se hace desde un contenedor efímero, que sí los lee.
# El .tar.gz queda como root pero con permisos de lectura: rclone puede subirlo
# y la rotación puede borrarlo, porque el directorio es de jmontero.
HA_NAME="homeassistant_$DATE.tar.gz"
if [ -d /opt/home-assistant ]; then
  if docker run --rm \
       -v /opt/home-assistant:/src:ro \
       -v "$BACKUP_DIR":/dst \
       alpine:latest \
       tar -czf "/dst/$HA_NAME" -C /src ha-config mosquitto 2>/dev/null; then
    echo "[$DATE] OK  home-assistant: $(du -sh "$BACKUP_DIR/$HA_NAME" | cut -f1) → $HA_NAME"
  else
    echo "[$DATE] ERROR: fallo el backup de home-assistant"
    rm -f "$BACKUP_DIR/$HA_NAME"
  fi
else
  echo "[$DATE] AVISO: /opt/home-assistant no existe, se omite"
fi

# ── 5. Rotación local ─────────────────────────────────────────────────────────
rotar() {
  local patron="$1"
  local cantidad
  cantidad=$(ls -1 $patron 2>/dev/null | wc -l)
  if [ "$cantidad" -gt "$MAX_BACKUPS" ]; then
    ls -1t $patron | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
    echo "[$DATE] Rotados: $(basename "$patron") — quedan $MAX_BACKUPS"
  fi
}

rotar "$BACKUP_DIR/mate_backup_*.tar.gz"
rotar "$BACKUP_DIR/cto_db_*.sql.gz"
rotar "$BACKUP_DIR/n8n_*.sql.gz"
rotar "$BACKUP_DIR/homeassistant_*.tar.gz"

# ── 6. Copia externa a OneDrive ───────────────────────────────────────────────
# Sin esto los backups viven en el mismo disco que los datos: si falla el disco,
# se pierden ambos. `sync` replica el estado local, incluida la rotación.
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q "^${RCLONE_REMOTE}:"; then
  echo "[$DATE] Sincronizando con OneDrive..."
  if rclone sync "$BACKUP_DIR" "${RCLONE_REMOTE}:${RCLONE_PATH}" \
       --exclude "*.log" \
       --transfers 2 \
       --retries 3 \
       --stats-one-line \
       2>&1 | sed "s/^/[$DATE] rclone: /"; then
    echo "[$DATE] OK  OneDrive sincronizado → ${RCLONE_PATH}"
  else
    echo "[$DATE] ERROR: fallo la sincronización con OneDrive"
  fi
else
  echo "[$DATE] AVISO: rclone no disponible o remote '${RCLONE_REMOTE}' sin configurar"
fi

echo "[$DATE] ===== Backup completado ====="
