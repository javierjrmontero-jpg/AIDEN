#!/bin/bash

# MATE — Script de backup automático
# Corre por cron todos los días a las 02:00
#
# Respalda:
#   1. MATE      → SQLite, ChromaDB, Neo4j, uploads, .env   (un solo .tar.gz)
#   2. cto_db    → contactos comerciales de CTO y AE        (pg_dump)
#   3. n8n       → flujos y credenciales de automatización  (pg_dump)
#
# Neo4j se detiene durante el tar: copiar sus archivos en caliente puede dejar
# un backup inconsistente. El trap garantiza que vuelva a levantar aunque el
# script falle a mitad de camino.

BACKUP_DIR="/home/jmontero/mate_backups"
AIDEN_DIR="/home/jmontero/aiden"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mate_backup_$DATE.tar.gz"
MAX_BACKUPS=7  # Mantener solo los últimos 7 de cada tipo

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

# ── 4. Rotación ───────────────────────────────────────────────────────────────
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

echo "[$DATE] ===== Backup completado ====="
