#!/bin/bash

# MATE — Script de backup automático
# Crea un backup comprimido de DB, vectorDB y documentos

BACKUP_DIR="/home/jmontero/mate_backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mate_backup_$DATE.tar.gz"
MAX_BACKUPS=7  # Mantener solo los últimos 7 backups

mkdir -p "$BACKUP_DIR"

echo "[$DATE] Iniciando backup de MATE..."

# Crear backup comprimido
tar -czf "$BACKUP_FILE" \
  -C /home/jmontero/aiden \
  data/db \
  data/vectordb \
  .env \
  2>/dev/null

if [ $? -eq 0 ]; then
  SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
  echo "[$DATE] Backup creado: $BACKUP_FILE ($SIZE)"
else
  echo "[$DATE] ERROR: Fallo al crear el backup"
  exit 1
fi

# Eliminar backups viejos manteniendo solo los últimos MAX_BACKUPS
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/mate_backup_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
  ls -1t "$BACKUP_DIR"/mate_backup_*.tar.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
  echo "[$DATE] Backups viejos eliminados. Manteniendo los últimos $MAX_BACKUPS"
fi

echo "[$DATE] Backup completado."
