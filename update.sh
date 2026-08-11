#!/bin/bash
# Despliega en la VM los cambios pusheados desde Windows.
# Detecta que cambio en el pull y reconstruye solo lo necesario.
#
# Uso:  cd ~/aiden && ./update.sh
set -e

cd ~/aiden

BEFORE=$(git rev-parse HEAD)

echo "[1/3] git pull..."
git pull origin main

AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    echo "=== Sin cambios nuevos. Nada que desplegar. ==="
    exit 0
fi

CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")
echo ""
echo "Archivos modificados:"
echo "$CHANGED" | sed 's/^/  /'
echo ""

echo "[2/3] Reconstruyendo lo que corresponde..."

# docker-compose.yml afecta a todos los servicios
if echo "$CHANGED" | grep -q "^docker-compose.yml"; then
    echo "  → docker-compose.yml cambio: aplicando a todos los servicios"
    docker compose up -d
else
    if echo "$CHANGED" | grep -q "^backend/"; then
        echo "  → backend"
        docker compose up -d --build backend
    fi
    # El frontend es Next.js en modo produccion: requiere build, no alcanza restart
    if echo "$CHANGED" | grep -q "^frontend/"; then
        echo "  → frontend (build + up)"
        docker compose build frontend
        docker compose up -d frontend
    fi
    if echo "$CHANGED" | grep -q "^nginx/"; then
        echo "  → nginx (recarga de config)"
        docker compose restart nginx
    fi
fi

echo ""
echo "[3/3] Verificando..."
sleep 5
docker compose ps
echo ""
curl -s -o /dev/null -w "Backend health: %{http_code}\n" http://localhost:8000/health || true
echo "=== Update OK ==="
