#!/bin/bash
# Actualiza AIDEN desde GitHub y reinicia el backend
set -e

cd ~/aiden
echo "[1/3] git pull..."
git pull origin main

echo "[2/3] Reiniciando backend..."
docker compose up -d --build backend

echo "[3/3] Verificando..."
sleep 5
docker compose ps backend
echo "=== Update OK ==="
