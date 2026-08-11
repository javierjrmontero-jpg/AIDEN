# Flujo de trabajo — AIDEN (backend MATE)

Regla única: **se edita en Windows, se despliega en la VM con `git pull`.**
No usar SCP. Copiar archivos sueltos a la VM ya provocó pisar código nuevo con versiones viejas.

## Dónde vive cada cosa

| | Ruta | Rol |
|---|---|---|
| Windows | `D:\aiden` | Donde se edita y se commitea |
| VM RHEL | `~/aiden` | Producción. Solo recibe `git pull` |
| GitHub | `javierjrmontero-jpg/AIDEN` | Fuente de verdad |

> `C:\Users\jmontero\OneDrive\...\AIDEN-copia-manual-20260810\` es un resguardo histórico,
> **no** un repo. No editar ahí ni copiar nada desde ahí.

## Ciclo normal

```powershell
# 1. En Windows — traer lo último antes de empezar
cd D:\aiden
git pull origin main

# 2. Editar, luego commitear y subir
git add <archivos>
git commit -m "tipo(alcance): descripción"
git push origin main
```

```bash
# 3. En la VM — desplegar
cd ~/aiden && ./update.sh
```

`update.sh` detecta qué cambió en el pull y reconstruye solo lo necesario:

| Cambió | Acción |
|---|---|
| `backend/` | `docker compose up -d --build backend` |
| `frontend/` | `build frontend` + `up -d frontend` (Next.js en producción: no alcanza restart) |
| `nginx/` | `restart nginx` |
| `docker-compose.yml` | `up -d` sobre todos los servicios |

## Antes de tocar producción

Respaldar datos y configuración:

```bash
BACKUP_DIR=~/backups/mate-$(date +%Y%m%d-%H%M); mkdir -p $BACKUP_DIR
cp ~/aiden/.env $BACKUP_DIR/env.bak
cp ~/aiden/data/db/aiden.db $BACKUP_DIR/aiden.db.bak
tar -czf $BACKUP_DIR/vectordb.tar.gz -C ~/aiden/data vectordb/
docker compose stop neo4j
tar -czf $BACKUP_DIR/neo4j.tar.gz -C ~/aiden/data/neo4j .
docker compose start neo4j
```

Neo4j necesita estar detenido para que el backup sea consistente.

## Cosas que muerden

- **Cloudflare devuelve 403 a clientes programáticos** en `mate.molmont.com.ar`
  (bloquea `User-Agent: Python-urllib/*`). Para scripts usar `mate.local` en LAN,
  o `http://localhost:8000` desde la propia VM.
- **`curl` desde la VM**: usar `http://localhost:8000`. Nginx no resuelve su propio hostname.
- **Nginx sirve varios proyectos**: además de MATE están `cto.molmont.com.ar` y `ae-web`.
  Un cambio en `nginx.conf` los afecta a los tres.
- **Cambios en `.env`**: `docker compose up -d backend` (no `restart`, que no relee el archivo).
- Contenedores: `aiden-backend`, `aiden-frontend`, `mate-neo4j`, `mate-nginx`.
  Backend y frontend **no** llevan el prefijo `mate-`.
