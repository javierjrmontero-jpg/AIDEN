# MATE — Checkpoint Ejecutivo
**Fecha:** 05/06/2026
**Versión:** Semana 10
**Autor:** Javier Montero (JJRM)
**Commit de cierre:** `25d6f4b` (rama `main`, repo AIDEN)

> Este checkpoint es **autosuficiente**: incorpora el estado heredado de la Semana 9 más todo lo nuevo de la Semana 10. No requiere consultar el checkpoint anterior para retomar.

---

## 1. Descripción del Proyecto

**MATE** (Motor de Asistencia Técnica e Inteligencia) es un asistente virtual personal estilo Jarvis sobre infraestructura propia, para uso personal y profesional, con horizonte de app nativa multiplataforma (Tauri). En la Semana 10 el foco fue **acción conversacional segura**: MATE ahora ejecuta acciones (crear eventos, tareas, enviar emails) directamente desde el chat mediante un **tool-loop**, con un **gate de confirmación** para el envío de emails (acción irreversible).

---

## 2. Infraestructura

| Componente | Detalle |
|---|---|
| Host | PC Windows 11 con VMware |
| VM | RHEL 10.2 (Coughlan) |
| RAM/CPU | 8GB RAM, 4 vCPU |
| Storage | 120GB NVMe |
| IP local (ens160) | 192.168.135.129 |
| IP local (ens224) | 192.168.1.92  ← **NUEVA, segunda NIC** |
| IP Tailscale | 100.74.230.46 |
| DNS local | mate.local (archivo hosts Windows → apunta a la IP de la VM) |
| Acceso | https://mate.local (HTTPS cert autofirmado) |
| Acceso remoto | Tailscale VPN → https://mate.local o https://100.74.230.46 |
| Proyecto server | ~/aiden/ |
| Repo server | https://github.com/javierjrmontero-jpg/AIDEN.git (SSH) |
| Repo desktop | https://github.com/javierjrmontero-jpg/mate-desktop.git |
| Dev tool | VS Code Remote SSH |

> Nota: el server expone dos subredes (`.135.x` y `.1.x`). `mate.local` resuelve a una de ellas vía hosts. Revisar que el acceso usado coincida con la NIC correcta.

---

## 3. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Frontend | Next.js 16.2.6 + Tailwind CSS — **modo producción** (`next build` + `next start`) |
| Base de datos | SQLite (aiosqlite + SQLAlchemy async) |
| Vector DB | ChromaDB 0.6.x |
| Embeddings | fastembed BAAI/bge-small-en-v1.5 |
| Voz (STT) | faster-whisper 1.2.1 (local, CPU, modelo `base`/int8) |
| LLM | Claude `claude-sonnet-4-5` (Anthropic API) |
| Proxy | Nginx (reverse proxy HTTPS) |
| Contenedores | Docker Compose |
| Búsqueda web | Brave Search API |
| Calendario | Google Calendar API (OAuth2) |
| Email | IMAP/SMTP (Gmail, basic) + Microsoft Graph (Outlook, OAuth2) |
| App escritorio | Tauri v2 (cliente fino) — repo `mate-desktop` |
| Acceso remoto | Tailscale |

---

## 4. Comandos Esenciales

```bash
# Levantar MATE
cd ~/aiden && docker compose up -d

# Logs
cd ~/aiden && docker compose logs backend -f
cd ~/aiden && docker compose logs frontend -f

# Reiniciar backend (dev, reload activo)
cd ~/aiden && docker compose restart backend

# .env: cambios requieren up -d (NO restart, no relee .env)
cd ~/aiden && docker compose up -d backend

# Frontend en PRODUCCIÓN: cada cambio requiere rebuild (NO hay hot-reload)
cd ~/aiden && docker compose build frontend && docker compose up -d frontend

# Validar sintaxis Python ANTES de reiniciar (evita ciclos de error)
docker compose exec backend python3 -m py_compile \
  app/services/llm/client.py app/services/agent/service.py \
  app/api/chat.py app/api/email.py && echo OK

# Commit y push (SSH configurado)
cd ~/aiden && git add . && git commit -m "mensaje" && git push origin main
```

**Acceso:** `https://mate.local` (web) o app de escritorio MATE (Tauri).

---

## 5. ★ NUEVO Semana 10 — Tool-loop en el chat

MATE ahora ejecuta herramientas **dentro del chat normal** (sin abrir el agente autónomo), conversando en lenguaje natural.

### Flujo (en `backend/app/services/llm/client.py`, función `stream_chat`)
1. Se arma el contexto (memorias, tareas, emails, calendario, RAG, web) — igual que antes.
2. Bucle `for _turn in range(MAX_TOOL_TURNS)` (tope = 5, anti-loop):
   - `client.messages.stream(..., tools=CHAT_TOOLS)` → se streamea el texto al frontend.
   - Al cerrar el stream: `final = stream.get_final_message()`.
   - Se agrega el turno `assistant` (texto + bloques `tool_use`) a la conversación.
   - Si `final.stop_reason != "tool_use"` → **break** (terminó).
   - Si hay `tool_use`: se ejecuta cada tool, se reinyecta un turno `user` con los `tool_result`, y se repite.
3. `yield "data: [DONE]"`.

### Herramientas habilitadas en chat (whitelist `CHAT_TOOLS`)
Se reutilizan los schemas y el executor `_execute_tool` del agente (DRY). Solo un **subconjunto seguro**:
```python
CHAT_TOOL_NAMES = {"get_calendar_events", "create_calendar_event", "send_email", "create_task"}
```
**`execute_python` / `execute_bash` quedan EXCLUIDOS del chat** a propósito: la ejecución de código por lenguaje natural debe quedar solo en el agente autónomo, invocado explícitamente. Sumar una tool al chat = agregar su nombre al set.

### Por qué reutilizar el agente
`agent/service.py` no importa `llm/client.py`, así que `from app.services.agent.service import RESEARCH_TOOLS, _execute_tool, _resolve_email_account, _account_label` no genera ciclo. Si en el futuro apareciera un ciclo, mover ese import dentro de `stream_chat`.

---

## 6. ★ NUEVO Semana 10 — Multi-cuenta de email (`from_account`)

Al sumar Outlook, hay **2 cuentas habilitadas** (gmail/basic + outlook/oauth). Esto rompió `scalar_one_or_none()` (error "Multiple rows were found"). Se corrigió y se agregó selección de cuenta.

### Helpers (en `agent/service.py`, a nivel módulo)
- `_account_label(cfg)`: etiqueta legible (intenta `email`/`email_address`/`username`/`google_email`/`address`, cae a `provider`).
- `_resolve_email_account(configs, hint)`:
  - sin hint + 1 cuenta → esa.
  - sin hint + N cuentas → `None` (hay que pedir aclaración).
  - con hint → match por etiqueta/proveedor/`auth_type` usando alias (`outlook`↔`hotmail`/`microsoft`/`graph`/`oauth`; `gmail`↔`google`/`basic`).
- Schema `send_email` incluye campo opcional `from_account`.

### Lectura de no leídos (en `llm/client.py`)
Se cambió `scalar_one_or_none()` por `scalars().all()` e itera **todas** las cuentas habilitadas agregando los no leídos (ya no falla con 2+ cuentas).

### Estado actual verificado (05/06/2026)
```
('514abb12-...','gmail','basic',  enabled=1)
('0d90e732-...','outlook','oauth',enabled=1)
```

---

## 7. ★ NUEVO Semana 10 — Gate de confirmación de email

`send_email` es la única acción del tool-loop con **efecto externo irreversible**. Se intercepta para que **nunca salga un mail sin aprobación explícita** del usuario.

### Arquitectura (stateless, compatible con SSE de un solo sentido)
1. En el tool-loop, si el modelo pide `send_email`, el backend **NO ejecuta**: resuelve la cuenta, arma el borrador y emite `[CONFIRM_EMAIL:{...}]` por SSE.
2. Devuelve al modelo un `tool_result` = *"borrador preparado, esperando confirmación, NO enviado"* → el modelo narra el borrador y avisa que falta confirmar.
3. El frontend muestra una **tarjeta modal** (Desde/Para/Asunto/Mensaje) con **Enviar / Cancelar**.
4. "Enviar" → `POST /api/v1/email/send-confirmed` → el backend **revalida** que la cuenta pertenece al usuario y recién ahí llama a `send_email`.

### Endpoint nuevo
`POST /api/v1/email/send-confirmed` — body `{to, subject, body, account_id}`, autenticado. Devuelve `{sent: bool, error?}`. No confía en el cliente: re-busca `EmailConfig` del usuario y matchea `account_id`.

### Frontend (`frontend/app/page.tsx`)
- Estado `pendingEmail` + `sendingEmail`.
- En el parser del stream: detecta `[CONFIRM_EMAIL:...]` → `setPendingEmail(draft)`. También **traga cualquier `[STATUS:...]`** (fix de un bug donde `[STATUS:tool:...]` se colaba como texto del mensaje).
- Función `confirmSendEmail()` → POST al endpoint + notificación (`success`/`error`).
- Tarjeta modal de revisión (solo lectura; editable es extensión futura trivial).

---

## 8. Contratos internos SSE (referencia para no releer código)

Todos los eventos viajan como `data: <json>\n\n`. El frontend hace `JSON.parse` del payload.

| Token | Origen | Significado | Manejo frontend |
|---|---|---|---|
| `"<texto>"` | llm/client | Delta de texto del asistente | Se concatena al último mensaje |
| `"[STATUS:searching]"` | llm/client | Inició búsqueda web | Muestra spinner "Buscando…" |
| `"[STATUS:done]"` | llm/client | Fin de búsqueda/tool | Oculta spinner |
| `"[STATUS:tool:<nombre>]"` | llm/client | Ejecutando herramienta | Se traga (no se renderiza); indicador opcional |
| `"[CONFIRM_EMAIL:{json}]"` | llm/client | Borrador de email a confirmar | Abre tarjeta de confirmación |
| `"[CONV:<id>]"` | api/chat | ID de conversación creada | Setea `conversationId` |
| `[DONE]` (sin comillas) | llm/client | Fin del stream | Corta el loop |

> El acumulador en `api/chat.py` (`stream_and_save`) excluye del texto guardado cualquier string que empiece con `[STATUS:` o `[CONFIRM_EMAIL:`.

---

## 9. Funcionalidades Implementadas (acumulado; ★ = nuevo Semana 10)

### Core
- Chat con streaming JSON-serializado + **★ tool-loop (ejecución de acciones en el chat)**
- Autenticación JWT, historial persistente, búsqueda en historial, exportación
- Separación de roles admin/usuario

### IA y Conocimiento
- RAG sobre documentos (PDF/DOCX/TXT/MD) + OCR (Tesseract)
- Memoria persistente entre conversaciones
- Búsqueda web automática (Brave)
- Multiidioma (es/en/pt/fr/de/it)

### Calendario
- Google Calendar OAuth2; lectura de agenda en chat y UI (`/calendar`); creación de eventos (UI + agente + **★ chat conversacional vía tool-loop**)

### Email
- IMAP/SMTP multi-cuenta (Gmail basic); Outlook vía Microsoft Graph (OAuth2 device code)
- **★ Multi-cuenta con `from_account`** (resolver con alias por proveedor/auth)
- **★ Envío conversacional desde el chat con gate de confirmación**
- **★ Endpoint `/email/send-confirmed`**

### Voz
- STT local faster-whisper; endpoint `/api/v1/transcribe` + `VoiceInput`; TTS

### Agente Autónomo
- Arquitectura dos fases (investigación → documento)
- Tools: web_search, execute_python, execute_bash, search_documents, read_memories, create_task, send_email (★ multi-cuenta), get_calendar_events, create_calendar_event

### UI/UX
- Markdown con syntax highlighting, copiar/descargar, sidebar, notificaciones (info/warning/error/success)
- **★ Tarjeta modal de confirmación de email**
- **★ Filtrado correcto de tokens `[STATUS:...]`**

### Infraestructura
- Nginx reverse proxy HTTPS + cert autofirmado; Tailscale; backups; Docker autostart
- Frontend en modo producción
- App de escritorio Tauri v2 (cliente fino)
- **★ Limpieza de warnings Next 16** (key `eslint` removida de `next.config.ts`; ESLint desactivado en build vía `NEXT_DISABLE_ESLINT=1`)

---

## 10. Decisiones Arquitectónicas (Semana 10)

| Decisión | Elección | Motivo |
|---|---|---|
| Acción en chat | **Tool-loop reutilizando executor del agente** | DRY; sin nueva integración, solo orquestación |
| Tools en chat | **Whitelist sin `execute_*`** | Ejecución de código por lenguaje natural = riesgo; queda solo en el agente |
| Envío de email | **Gate de confirmación (no auto-envío)** | Acción irreversible; aprobación explícita del usuario |
| Pausa para confirmar | **Marcador SSE + endpoint separado** | SSE es unidireccional; no se puede bloquear el stream esperando un click |
| Selección de cuenta | **`from_account` + resolver con alias** | 2 cuentas activas; matchea por proveedor/auth aunque la dirección difiera |
| Lectura no leídos | **`scalars().all()` iterando cuentas** | `scalar_one_or_none()` falla con 2+ cuentas |
| Lint en build | **`NEXT_DISABLE_ESLINT=1` en Dockerfile** | Next 16 deprecó la key `eslint` en `next.config.ts` |

---

## 11. Variables de Entorno (.env)

```
ANTHROPIC_API_KEY=...
BRAVE_SEARCH_API_KEY=...
SEARCH_ENABLED=True
ANONYMIZED_TELEMETRY=False
CHROMA_TELEMETRY=False
SECRET_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...     # client público, sin secret
WHISPER_MODEL=base          # base|small|tiny
```

> Cambios en `.env` requieren `docker compose up -d backend` (un `restart` no relee el `.env`).

---

## 12. Modelo de Datos (estado actual)

| Tabla | Columnas relevantes |
|---|---|
| `calendar_configs` | user_id, provider, google_email, refresh_token, calendar_id, enabled |
| `email_configs` | + `auth_type` (default 'basic'), + `oauth_refresh_token` |

Migración email_configs (idempotente, ya aplicada):
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

## 13. Archivos Tocados (Semana 10)

### Backend
- MOD `backend/app/services/llm/client.py` — tool-loop en chat (`CHAT_TOOLS`, bucle `stop_reason`), gate de email (intercepta `send_email` → `[CONFIRM_EMAIL:...]`), lectura multi-cuenta de no leídos, instrucciones de tools en SYSTEM_PROMPT
- MOD `backend/app/services/agent/service.py` — helpers `_account_label` / `_resolve_email_account`, alias `_ACCOUNT_ALIASES`, schema `send_email` con `from_account`, rama `send_email` con selección de cuenta
- MOD `backend/app/api/chat.py` — acumulador excluye `[CONFIRM_EMAIL:...]` además de `[STATUS:...]`
- MOD `backend/app/api/email.py` — endpoint `POST /email/send-confirmed` (revalida cuenta del usuario)

### Frontend
- MOD `frontend/app/page.tsx` — estado `pendingEmail`/`sendingEmail`, detección `[CONFIRM_EMAIL:...]`, filtrado de `[STATUS:...]`, `confirmSendEmail()`, tarjeta modal de confirmación
- MOD `frontend/next.config.ts` — removida key `eslint` (deprecada en Next 16)
- MOD `frontend/Dockerfile` — `ENV NEXT_DISABLE_ESLINT=1` antes de `npm run build`

---

## 14. Setup OAuth (referencia rápida)

### Google Calendar
1. console.cloud.google.com → habilitar Google Calendar API
2. OAuth consent screen → **publicar en producción** (en Testing el refresh token expira a 7 días)
3. Credentials → OAuth client ID → **Desktop app** → client_id + secret a `.env`
4. `python scripts/google_calendar_auth.py` (PC) → pegar refresh token en `/calendar`

### Outlook (Microsoft Graph)
1. entra.microsoft.com → App registrations → "Personal Microsoft accounts"
2. Authentication → **Allow public client flows = Yes**
3. API permissions → Graph delegated: Mail.Read, Mail.Send, User.Read, offline_access
4. `python scripts/microsoft_email_auth.py` (PC) → microsoft.com/devicelogin → pegar refresh token en `/email`

### Desktop (Tauri, PC Windows 11)
Prerrequisitos: Node 24.16, C++ Build Tools VS2022, Rust 1.96, WebView2 (preinstalado). Cert `mate.local.crt` importado en "Entidades de certificación raíz de confianza".

---

## 15. Notas Técnicas Importantes (acumulado + nuevas)

- `API_URL = ""` en frontend (rutas relativas vía Nginx)
- Streaming usa `json.dumps/json.loads`
- Embeddings y Whisper se cachean en `data/models`; primera carga lenta
- Ruta `/conversations/search` debe ir ANTES de `/conversations/{id}`
- Sandbox: `docker run --rm --network none`
- Tailscale `tailscale0` en zona `trusted`
- **`.env`: usar `up -d`, NO `restart`**
- **Frontend en producción: cada cambio requiere `build frontend && up -d`** (backend sigue en dev con reload)
- Microsoft auth básica IMAP/SMTP deprecada (límite abril 2026) → Outlook va por Graph
- Whisper: BCP-47 ('es-AR') se recorta a ISO 639-1 ('es') en el endpoint
- Tauri + cert autofirmado: confiar el cert en Windows para que WebView2 no rechace mate.local
- SIEMPRE `git push origin main` después de cada commit
- **★ Telemetría ChromaDB 0.6.x** lanza `Failed to send telemetry... capture() takes 1 positional argument` en logs: **inofensivo**, no afecta RAG. Se silencia actualizando Chroma (validar compatibilidad antes).
- **★ Tool-loop:** tope `MAX_TOOL_TURNS=5` por turno de chat
- **★ Para sumar una tool al chat:** agregar su nombre a `CHAT_TOOL_NAMES` en `llm/client.py`
- **★ El gate frena el envío en backend** aunque el frontend no muestre la tarjeta (defensa en profundidad)

---

## 16. Lecciones Operativas

- **Pegado parcial de bloques = fuente principal de errores** (se cuela prosa o se desalinea la indentación). Mitigación: copiar desde archivos `.py`/`.tsx` completos, alinear ramas `elif` a 8 espacios, y correr `py_compile` ANTES de reiniciar.
- **`scalar_one_or_none()` asume 0/1 fila** — usar `scalars().all()` cuando un usuario puede tener N registros (cuentas de email).
- **Tokens de control SSE nuevos** deben filtrarse en AMBOS lados (backend accumulator + frontend parser) o se renderizan como texto.
- **Restaurar archivo pisado:** `git checkout -- <archivo>`.

---

## 17. Pendientes / Backlog

| Feature | Prioridad | Estado |
|---|---|---|
| Empaquetado fase 2: icono + system tray + instalador `.msi` (Tauri) | Media | ⏳ **Siguiente sugerido** — pasos ya documentados (sección 18) |
| Indicador de tool en el chat ("Ejecutando crear evento…") | Baja | ⏳ Trivial ahora (token `[STATUS:tool:...]` ya llega limpio) |
| Tarjeta de email **editable** (corregir asunto/cuerpo antes de enviar) | Baja | ⏳ Extensión simple |
| Sumar tools read-only al chat (search_documents, read_memories) | Baja | ⏳ Agregar al whitelist |
| Persistir tool-calls en el historial (auditoría/trazabilidad) | Media | ⏳ Definir formato primero |
| Limpiar `allowedDevOrigins` en `next.config.ts` (192.168.2.128 obsoleta) | Baja | ⏳ Cosmético (solo afecta dev) |
| Rotación/expiración de refresh tokens (Google prod, MS ~90 días) | Baja | ⏳ Monitorear |
| Selección de cuenta de origen para email también en agente | Baja | ⏳ Si se usan ambas para enviar |

---

## 18. Empaquetado Fase 2 (Tauri v2) — pasos listos para PC Windows

Sobre el repo `mate-desktop` (server no se toca).

```bash
# 1) Icono (PNG cuadrado >=1024x1024)
cd mate-desktop
npm run tauri icon ./logo.png

# 2) System tray: en src-tauri/Cargo.toml
#    tauri = { version = "2", features = ["tray-icon", "image-png"] }
#    y en src-tauri/src/lib.rs, dentro de .setup(|app| { ... }):
#      TrayIconBuilder con menú "Abrir MATE" / "Salir" y on_menu_event
#      (abrir -> get_webview_window("main").show()+set_focus(); salir -> app.exit(0))

# 3) Instalador .msi
npm run tauri build
#    salida: src-tauri/target/release/bundle/msi/
```

Riesgos: `.msi` sin firmar dispara SmartScreen (aceptable uso personal); subir `version` en `tauri.conf.json` antes de cada build; cert `mate.local.crt` debe importarse en cada PC destino.

---

## 19. Próximos Pasos al Retomar

1. **Empaquetado fase 2** (Tauri): icono + system tray + `.msi` (sección 18).
2. Opcional rápido: indicador de tool en chat / tarjeta de email editable.
3. Validar expiración de tokens OAuth a largo plazo (reconexión si caducan).

---

## 20. Próximo Prompt Recomendado

```
Retomamos MATE (Motor de Asistencia Técnica e Inteligencia). Adjunto el
checkpoint Semana 10. Server (FastAPI + Next.js 16 producción + SQLite + Docker
en RHEL 10) en ~/aiden (repo AIDEN, commit 25d6f4b). App de escritorio Tauri en
repo mate-desktop (PC Windows).

Operativos: Google Calendar, Outlook vía Graph, voz Whisper local, agente de dos
fases, y NUEVO: tool-loop en el chat (crear eventos/tareas/enviar mail conversando),
email multi-cuenta con from_account, y gate de confirmación de envío de email
(marcador SSE [CONFIRM_EMAIL] + endpoint /email/send-confirmed).

Próximo paso: empaquetado fase 2 de Tauri (icono + system tray + instalador .msi).

Recordá las reglas: frontend en producción (build + up -d por cada cambio),
.env con up -d (no restart), validar con py_compile antes de reiniciar, y
git push origin main después de cada commit. Tools de chat en whitelist
CHAT_TOOL_NAMES (sin execute_*). MAX_TOOL_TURNS=5.
```

---

*Checkpoint generado por MATE · Motor de Asistencia Técnica e Inteligencia by JJRM*
