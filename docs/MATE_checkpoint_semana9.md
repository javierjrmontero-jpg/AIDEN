# MATE — Checkpoint Ejecutivo
**Fecha:** 02/06/2026
**Versión:** Semana 9
**Autor:** Javier Montero (JJRM)

---

## 1. Descripción del Proyecto

**MATE** (Motor de Asistencia Técnica e Inteligencia) es un asistente virtual personal estilo Jarvis, construido sobre infraestructura propia. Diseñado para uso personal y profesional, con horizonte de convertirse en aplicación nativa multiplataforma (Tauri). En esta semana se incorporó el **primer shell de escritorio funcional** (cliente fino sobre Tauri v2).

---

## 2. Infraestructura

| Componente | Detalle |
|---|---|
| Host | PC Windows 11 con VMware |
| VM | RHEL 10.2 (Coughlan) |
| RAM/CPU | 8GB RAM, 4 vCPU |
| Storage | 120GB NVMe |
| IP local | 192.168.135.129 |
| IP Tailscale | 100.74.230.46 |
| DNS local | mate.local (archivo hosts Windows) |
| Acceso | https://mate.local (HTTPS cert autofirmado) |
| Acceso remoto | Tailscale VPN → https://mate.local o https://100.74.230.46 |
| Proyecto server | ~/aiden/ |
| Repo server | https://github.com/javierjrmontero-jpg/AIDEN.git (SSH) |
| Repo desktop | https://github.com/javierjrmontero-jpg/mate-desktop.git (NUEVO) |
| Dev tool | VS Code Remote SSH |

---

## 3. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Frontend | Next.js 16 + Tailwind CSS — **modo producción** (`next build` + `next start`) |
| Base de datos | SQLite (aiosqlite + SQLAlchemy async) |
| Vector DB | ChromaDB 0.6.x |
| Embeddings | fastembed BAAI/bge-small-en-v1.5 |
| Voz (STT) | **faster-whisper 1.2.1 (local, CPU, modelo `base`/int8)** |
| LLM | Claude claude-sonnet-4-5 (Anthropic API) |
| Proxy | Nginx (reverse proxy HTTPS) |
| Contenedores | Docker Compose |
| Búsqueda web | Brave Search API |
| Calendario | **Google Calendar API (OAuth2)** |
| Email | IMAP/SMTP (Gmail) + **Microsoft Graph (Outlook OAuth2)** |
| App escritorio | **Tauri v2 (cliente fino) — repo `mate-desktop`** |
| Acceso remoto | Tailscale |

---

## 4. Comandos Esenciales

```bash
# Levantar MATE
cd ~/aiden && docker compose up -d

# Ver logs backend / frontend
cd ~/aiden && docker compose logs backend -f
cd ~/aiden && docker compose logs frontend -f

# Reiniciar backend (dev, reload activo)
cd ~/aiden && docker compose restart backend

# IMPORTANTE: cambios en .env requieren up -d (NO restart, no relee .env)
cd ~/aiden && docker compose up -d backend

# Frontend en PRODUCCIÓN: cada cambio requiere rebuild (NO hay hot-reload)
cd ~/aiden && docker compose build frontend && docker compose up -d frontend

# Verificar sintaxis Python ANTES de reiniciar (evita ciclos de error)
python3 -m py_compile backend/app/api/*.py backend/app/services/**/*.py && echo OK

# Commit y push (SSH configurado, no pide credenciales)
cd ~/aiden && git add . && git commit -m "mensaje" && git push origin main
```

**Acceso:** `https://mate.local` (web) o app de escritorio MATE (Tauri).

---

## 5. Funcionalidades Implementadas (nuevas en Semana 9 marcadas con ★)

### Core
- Chat con streaming JSON-serializado
- Autenticación JWT, historial persistente, búsqueda en historial, exportación
- Separación de roles admin/usuario (is_admin)

### IA y Conocimiento
- RAG sobre documentos (PDF/DOCX/TXT/MD) + OCR (Tesseract)
- Memoria persistente entre conversaciones
- Búsqueda web automática (Brave)
- Multiidioma (es/en/pt/fr/de/it)

### Calendario ★
- ★ Conexión Google Calendar vía OAuth2 (refresh token por usuario)
- ★ Lectura de agenda en el chat (inyección de contexto) y en la UI (`/calendar`)
- ★ Creación de eventos desde la UI y desde el agente autónomo
- ★ Normalización RFC3339 de fechas (segundos, día completo)

### Email ★
- IMAP/SMTP multi-cuenta (Gmail, auth básica con App Password)
- ★ Outlook/Hotmail vía Microsoft Graph (OAuth2, device code flow)
- ★ Lectura (inbox/no leídos) y envío vía Graph — no depende de IMAP/SMTP
- ★ Dispatch automático IMAP vs Graph según `auth_type` (firmas sin cambios)

### Voz ★
- ★ STT local con faster-whisper (reemplaza Web Speech API del navegador)
- ★ Endpoint `/api/v1/transcribe` + componente `VoiceInput` con MediaRecorder
- TTS (texto→voz)

### Agente Autónomo
- Arquitectura dos fases (investigación → documento)
- Herramientas: web_search, execute_python, execute_bash, search_documents,
  read_memories, create_task, send_email, ★ get_calendar_events, ★ create_calendar_event

### Productividad
- Tareas y recordatorios con prioridad/fecha; alertas de vencidas
- Estadísticas personales

### Código
- Sandbox Docker aislado Python / JavaScript / Bash

### UI/UX
- Markdown con syntax highlighting, copiar/descargar, sidebar, notificaciones
- ★ Link a Calendario en el menú lateral
- ★ Fix de scroll vertical global (overflow-y) — páginas largas
- ★ Fix `tasks.forEach` (Array.isArray guard)
- Atajos de teclado, responsive mobile

### Infraestructura ★
- Nginx reverse proxy HTTPS + cert autofirmado mate.local
- Tailscale VPN, arranque automático Docker, backups
- ★ Frontend en modo producción (elimina glitches de Turbopack)
- ★ App de escritorio Tauri v2 (cliente fino)

---

## 6. Decisiones Arquitectónicas (Semana 9)

| Decisión | Elección | Motivo |
|---|---|---|
| OAuth Google (redirect) | Cliente Desktop + script bootstrap → refresh token | Google rechaza redirect URIs `.local` e IPs |
| OAuth Microsoft | Device code flow | No requiere redirect URI; evita el problema del `.local` |
| Outlook: IMAP vs Graph | **Microsoft Graph** | Cuentas consumer tienen SMTP AUTH deshabilitado server-side; Graph no depende de IMAP/SMTP |
| Email auth | Campo `auth_type` (basic/oauth) + dispatch interno | Reutiliza servicio existente; firmas sin cambios → no toca agente ni llm |
| Voz STT | faster-whisper local (CPU, int8) | Independiza del navegador; alineado a app nativa |
| Empaquetado | **Cliente fino** (no embebido) | Aprovecha el server existente; embebido = esfuerzo desproporcionado |
| Framework desktop | **Tauri v2** (no Electron) | App liviana (~MB), bajo RAM, seguro; coherente con perfil |
| Frontend dev/prod | Producción (`next build`+`start`) | Turbopack (default en Next 16) generaba 404 de hidratación y caché inconsistente |

---

## 7. Variables de Entorno (.env)

```
ANTHROPIC_API_KEY=...
BRAVE_SEARCH_API_KEY=...
SEARCH_ENABLED=True
ANONYMIZED_TELEMETRY=False
CHROMA_TELEMETRY=False
SECRET_KEY=...
GOOGLE_CLIENT_ID=...            # NUEVO (Calendar)
GOOGLE_CLIENT_SECRET=...        # NUEVO (Calendar)
MICROSOFT_CLIENT_ID=...         # NUEVO (Outlook/Graph) — client público, sin secret
WHISPER_MODEL=base              # NUEVO (voz) — base|small|tiny
```

> Nota: cambios en `.env` requieren `docker compose up -d backend` (un `restart` no relee el `.env`).

---

## 8. Cambios en el Modelo de Datos

| Tabla | Cambio | Migración |
|---|---|---|
| `calendar_configs` | NUEVA (user_id, provider, google_email, refresh_token, calendar_id, enabled) | Auto vía create_all |
| `email_configs` | + `auth_type` (default 'basic'), + `oauth_refresh_token` | Manual: `ALTER TABLE` |

Comando de migración usado (idempotente):
```bash
docker compose exec backend python3 -c "
import sqlite3
db = sqlite3.connect('/data/db/aiden.db')
for stmt in [
    \"ALTER TABLE email_configs ADD COLUMN auth_type TEXT DEFAULT 'basic'\",
    \"ALTER TABLE email_configs ADD COLUMN oauth_refresh_token TEXT\",
]:
    try: db.execute(stmt); print('OK:', stmt)
    except Exception as e: print('SKIP:', e)
db.commit(); db.close()
"
```

---

## 9. Archivos Nuevos / Modificados (Semana 9)

### Backend
- NUEVO `backend/app/models/calendar_config.py`
- NUEVO `backend/app/services/calendar/{__init__,service}.py`
- NUEVO `backend/app/api/calendar.py`
- NUEVO `backend/app/services/voice/{__init__,service}.py`
- NUEVO `backend/app/api/voice.py`
- NUEVO `backend/app/services/email/graph.py`
- MOD `backend/app/services/email/service.py` (dispatch IMAP/Graph; SMTP consumer = smtp-mail.outlook.com)
- MOD `backend/app/api/email.py` (endpoint `/email/config/outlook`)
- MOD `backend/app/models/email_config.py` (auth_type, oauth_refresh_token)
- MOD `backend/app/services/agent/service.py` (tools de calendario)
- MOD `backend/app/services/llm/client.py` (contexto de agenda en chat)
- MOD `backend/app/core/config.py` (GOOGLE_*, MICROSOFT_CLIENT_ID, WHISPER_MODEL)
- MOD `backend/app/main.py` (routers calendar, voice)
- MOD `backend/requirements.txt` (google-api-python-client 2.197, google-auth 2.53, google-auth-oauthlib 1.4, google-auth-httplib2 0.4, faster-whisper 1.2.1)

### Frontend
- NUEVO `frontend/app/calendar/page.tsx`
- MOD `frontend/components/VoiceInput.tsx` (MediaRecorder → backend)
- MOD `frontend/app/email/page.tsx` (tarjeta Conectar Outlook; selector basic sin Outlook)
- MOD `frontend/app/page.tsx` (link Calendario; fix tasks.forEach)
- MOD `frontend/app/globals.css` (overflow-y auto)
- MOD `frontend/Dockerfile` (build de producción)
- MOD `frontend/next.config.ts` (ignore build errors TS/ESLint)
- MOD `docker-compose.yml` (frontend sin volumen de código)

### Scripts (one-time, ejecutados en PC)
- NUEVO `scripts/google_calendar_auth.py` (loopback, genera refresh token Google)
- NUEVO `scripts/microsoft_email_auth.py` (device code flow, genera refresh token MS)

### Proyecto desktop (repo separado `mate-desktop`)
- Tauri v2, cliente fino que carga `https://mate.local` en ventana nativa
- `src-tauri/tauri.conf.json`: `devUrl`/`frontendDist`/`windows[].url` → https://mate.local
- Cert `mate.local.crt` **excluido del repo** (en .gitignore)

---

## 10. Setup OAuth (referencia rápida)

### Google Calendar
1. console.cloud.google.com → habilitar Google Calendar API
2. OAuth consent screen → **publicar en producción** (en Testing el refresh token expira a 7 días)
3. Credentials → OAuth client ID → **Desktop app** → client_id + secret a `.env`
4. `python scripts/google_calendar_auth.py` (PC) → pegar refresh token en `/calendar` → Conexión

### Outlook (Microsoft Graph)
1. entra.microsoft.com → App registrations → cuenta "Personal Microsoft accounts"
2. Authentication → **Allow public client flows = Yes**
3. API permissions → Graph delegated: Mail.Read, Mail.Send, User.Read, offline_access
4. `python scripts/microsoft_email_auth.py` (PC) → código en microsoft.com/devicelogin → pegar refresh token en `/email` → tarjeta "Conectar Outlook"

### Desktop (Tauri, en la PC Windows 11)
Prerrequisitos: Node 20+ (instalado v24.16), C++ Build Tools VS2022, Rust (rustc 1.96), WebView2 (preinstalado en Win11). Cert `mate.local.crt` importado en "Entidades de certificación raíz de confianza".

---

## 11. Notas Técnicas Importantes (acumulado + nuevas)

- `API_URL = ""` en frontend (rutas relativas via Nginx)
- Streaming usa `json.dumps/json.loads`
- Embeddings y Whisper se cachean en `data/models` (mount a /root/.cache/huggingface); primera carga lenta
- Ruta `/conversations/search` debe ir ANTES de `/conversations/{id}`
- Sandbox: `docker run --rm --network none`
- Tailscale `tailscale0` en zona `trusted`
- **`.env`: usar `up -d`, NO `restart`** (restart no relee variables de entorno)
- **Frontend en producción: cada cambio requiere `build frontend && up -d`** (no hay hot-reload). Backend sigue en dev con reload.
- **Microsoft auth básica IMAP/SMTP: deprecada (fecha límite abril 2026)** → Outlook va por Graph
- Whisper: BCP-47 ('es-AR') se recorta a ISO 639-1 ('es') en el endpoint
- Tauri + cert autofirmado: hay que **confiar el cert** en Windows para que WebView2 no rechace mate.local
- SIEMPRE `git push origin main` después de cada commit

---

## 12. Lecciones de la Sesión (operativas)

- **Pegado manual de archivos = fuente principal de errores** (se colaron `k"""`, imports cruzados, y se pisó `chat.py`). Mitigación: subir archivos por VS Code Remote o pegar con **Ctrl+Shift+V**, y correr `py_compile` ANTES de reiniciar.
- **Restaurar archivos pisados con Git:** `git checkout -- <archivo>` (ej. `chat.py`).
- **Errores comunes resueltos:** `.local` rechazado por Google (→ device/desktop flow), SMTP AUTH consumer deshabilitado (→ Graph), código device ≠ refresh token, `client_id` vacío (→ `up -d`).

---

## 13. Pendientes / Backlog

| Feature | Prioridad | Estado |
|---|---|---|
| Tool-loop en el chat (crear eventos / enviar mail por lenguaje natural) | Media | ⏳ Siguiente sugerido |
| Empaquetado fase 2: icono propio + system tray + instalador `.msi` | Media | ⏳ Pendiente |
| Rotación/expiración de refresh tokens (Google prod, MS ~90 días) | Baja | ⏳ Monitorear |
| Tauri → distribución (Tailscale + cert para otras PCs) | Baja | ⏳ Fase futura |
| Migrar config.py a lectura robusta de .env si reaparece vacío | Baja | ⏳ Si recurre |
| Voz: activar VAD / modelo `small` si se quiere más calidad | Baja | ⏳ Opcional |

---

## 14. Próximos Pasos al Retomar

1. **Empaquetado fase 2** — `npm run tauri icon <logo>`, system tray, `npm run tauri build` (.msi)
2. **Tool-loop en el chat** — que MATE cree eventos/mande mails conversando, sin abrir el agente
3. Validar expiración de tokens a largo plazo (reconexión si caducan)

---

## 15. Próximo Prompt Recomendado

```
Retomamos MATE (Motor de Asistencia Técnica e Inteligencia). Te adjunto el
checkpoint Semana 9. El server (FastAPI + Next.js producción + SQLite + Docker
en RHEL 10) está en ~/aiden (repo AIDEN). La app de escritorio Tauri está en
repo separado mate-desktop. Ya están operativos: Google Calendar, Outlook vía
Graph, voz Whisper local y el shell Tauri (cliente fino).
Próximo paso: empaquetado fase 2 (icono + system tray + instalador .msi) o
tool-loop en el chat. Recordá: frontend en producción (build+up -d por cambio),
.env con up -d (no restart), y git push después de cada commit.
```

---

*Checkpoint generado por MATE · Motor de Asistencia Técnica e Inteligencia by JJRM*
