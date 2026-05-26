# MATE — Checkpoint Ejecutivo
**Fecha:** 26/05/2026  
**Versión:** Semana 7+  
**Autor:** Javier Montero (JJRM)

---

## 1. Descripción del Proyecto

**MATE** (Motor de Asistencia Técnica e Inteligencia) es un asistente virtual personal estilo Jarvis, construido sobre infraestructura propia. Diseñado para uso personal y profesional, con horizonte de convertirse en aplicación nativa multiplataforma (Electron/Tauri).

---

## 2. Infraestructura

| Componente | Detalle |
|---|---|
| Host | PC Windows con VMware |
| VM | RHEL 10.2 (Coughlan) |
| RAM/CPU | 8GB RAM, 4 vCPU |
| Storage | 120GB NVMe |
| IP local | 192.168.135.129 |
| IP Tailscale | 100.74.230.46 |
| DNS local | mate.local (archivo hosts Windows) |
| Acceso | https://mate.local (HTTPS cert autofirmado) |
| Acceso remoto | Tailscale VPN → https://mate.local o https://100.74.230.46 |
| Proyecto | ~/aiden/ |
| Dev tool | VS Code Remote SSH |

---

## 3. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Frontend | Next.js + Tailwind CSS |
| Base de datos | SQLite (aiosqlite + SQLAlchemy async) |
| Vector DB | ChromaDB 0.6.x |
| Embeddings | fastembed BAAI/bge-small-en-v1.5 |
| LLM | Claude claude-sonnet-4-5 (Anthropic API) |
| Proxy | Nginx (reverse proxy HTTPS) |
| Contenedores | Docker Compose |
| Búsqueda web | Brave Search API |
| Acceso remoto | Tailscale |

---

## 4. Comandos Esenciales

```bash
# Levantar MATE
cd ~/aiden && docker compose up -d

# Ver logs backend
cd ~/aiden && docker compose logs backend -f

# Reiniciar backend
cd ~/aiden && docker compose restart backend

# Backup manual
~/aiden/scripts/backup.sh
```

**Acceso:** `https://mate.local`

---

## 5. Estructura del Proyecto

```
~/aiden/
├── backend/
│   ├── app/
│   │   ├── api/           # auth, chat, conversations, documents, generate,
│   │   │                  # memories, sandbox, admin, tasks, email, stats, agent
│   │   ├── models/        # user, conversation, document, memory, task,
│   │   │                  # email_config, agent_task
│   │   ├── services/
│   │   │   ├── llm/       # client.py — sistema prompt + RAG + memorias + tareas + emails
│   │   │   ├── rag/       # service.py — ChromaDB + embeddings + OCR
│   │   │   ├── search/    # service.py — Brave Search API
│   │   │   ├── memory/    # service.py — extracción y gestión de memorias
│   │   │   ├── email/     # service.py — IMAP/SMTP multi-cuenta
│   │   │   ├── sandbox/   # service.py — ejecución código Docker aislado
│   │   │   └── agent/     # service.py — agente autónomo dos fases
│   │   └── core/          # config, database, auth
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx       # Chat principal
│   │   ├── login/         # Login/registro
│   │   ├── profile/       # Perfil + idioma
│   │   ├── documents/     # Gestión de documentos RAG
│   │   ├── memories/      # Visualización de memorias
│   │   ├── tasks/         # Tareas y recordatorios
│   │   ├── email/         # Cliente de email multi-cuenta
│   │   ├── stats/         # Estadísticas personales
│   │   ├── agent/         # Agente autónomo
│   │   └── admin/         # Panel de administración
│   └── components/
│       ├── MarkdownRenderer.tsx
│       ├── MessageActions.tsx
│       ├── CodeExecutor.tsx
│       ├── VoiceInput.tsx
│       ├── useTTS.tsx
│       ├── Notification.tsx
│       └── useNotifications.tsx
├── nginx/
│   ├── nginx.conf         # server_name _ (acepta cualquier hostname/IP)
│   └── certs/             # Certificado autofirmado mate.local
├── data/
│   ├── db/aiden.db        # SQLite
│   ├── vectordb/          # ChromaDB
│   └── models/            # Caché embeddings (persistente)
├── scripts/
│   └── backup.sh          # Backup automático
└── docker-compose.yml
```

---

## 6. Funcionalidades Implementadas

### Core
- ✅ Chat con streaming JSON-serializado
- ✅ Autenticación JWT (login/registro)
- ✅ Historial de conversaciones persistente
- ✅ Búsqueda en historial por título y contenido
- ✅ Exportación de conversaciones (MD/TXT/JSON)
- ✅ Separación de roles admin/usuario (campo `is_admin`)

### IA y Conocimiento
- ✅ RAG sobre documentos (PDF/DOCX/TXT/MD)
- ✅ OCR automático para PDFs escaneados (Tesseract, español+inglés)
- ✅ Memoria persistente entre conversaciones (extracción automática por Claude)
- ✅ Búsqueda web automática con Brave Search API (trigger por palabras clave)
- ✅ Indicador visual "Buscando en la web..."
- ✅ Multiidioma estricto (es/en/pt/fr/de/it) desde perfil

### Productividad
- ✅ Tareas y recordatorios con prioridad y fecha límite
- ✅ Alertas de tareas vencidas (verificación cada 5 minutos)
- ✅ Email multi-cuenta Gmail (IMAP/SMTP con App Password)
- ✅ Outlook bloqueado por Microsoft (OAuth2 pendiente)
- ✅ Estadísticas personales con gráfico de actividad

### Código
- ✅ Sandbox Docker aislado Python (azul) / JavaScript (amarillo) / Bash (gris)
- ✅ Sin acceso a red ni filesystem del host, timeout 15s
- ✅ Botón ▶ Ejecutar en cada bloque de código

### UI/UX
- ✅ Markdown con syntax highlighting (react-markdown + react-syntax-highlighter)
- ✅ Botones copiar/descargar MD/TXT/HTML en respuestas (SVG icons)
- ✅ Sidebar con búsqueda, botones SVG, grid de navegación
- ✅ Sistema de notificaciones con animación (Notification + useNotifications)
- ✅ Alerta cuando crédito Brave Search < 20%
- ✅ Voz STT (micrófono → texto) y TTS (texto → voz) via Web Speech API
- ✅ Scrollbar estilizada, body overflow hidden

### Infraestructura
- ✅ Nginx reverse proxy HTTPS (server_name _ para cualquier hostname)
- ✅ Certificado autofirmado mate.local
- ✅ DNS local mate.local (archivo hosts Windows)
- ✅ Tailscale VPN para acceso remoto (interfaz tailscale0 en zona trusted)
- ✅ Arranque automático Docker + contenedores al reiniciar VM
- ✅ Backup automático diario 2AM (cron) + manual desde panel admin
- ✅ Panel de administración: stats, usuarios, conversaciones, backups, consumo Brave

---

## 7. Decisiones Arquitectónicas Tomadas

| Decisión | Elección | Motivo |
|---|---|---|
| Base de datos | SQLite | Simplicidad, sin dependencias externas |
| Vector DB | ChromaDB | Local, sin cloud, privacy-first |
| LLM | Claude claude-sonnet-4-5 | Calidad y API confiable |
| Búsqueda web | Brave Search | Privacidad, índice propio, USD 5 crédito/mes |
| Proxy | Nginx | Estándar de producción, liviano |
| Contenedores | Docker Compose | Portabilidad y aislamiento |
| Acceso remoto | Tailscale | Sin configurar router, VPN mesh simple |
| App futura | Electron/Tauri | Empaquetar Next.js existente sin reescribir |
| Email Outlook | Pendiente OAuth2 | Microsoft bloqueó auth básica en 2023 |

---

## 8. Variables de Entorno (.env)

```
ANTHROPIC_API_KEY=...
BRAVE_SEARCH_API_KEY=...
SEARCH_ENABLED=True
ANONYMIZED_TELEMETRY=False
CHROMA_TELEMETRY=False
SECRET_KEY=...
```

---

## 9. Usuarios en el Sistema

| Usuario | Email | Rol |
|---|---|---|
| Javier Montero | javierjrmontero@outlook.com | Admin (is_admin=1) |
| Silvana Molinero | smolinero@outlook.com | Usuario normal |

---

## 10. Estado Actual — En Progreso

### Agente Autónomo (🔄 debugging)
El agente usa arquitectura de dos fases:
1. **Fase investigación**: búsquedas web con RESEARCH_TOOLS
2. **Fase documento**: llamada forzada con `tool_choice: create_document`

**Problema actual**: la fase 2 lanza `Error generando documento: 'content'` — el `block.input` no está siendo parseado correctamente. El último fix agrega manejo de `isinstance(block.input, dict)` vs objeto. Pendiente verificar si resuelve.

**Archivo en edición**: `backend/app/services/agent/service.py`

---

## 11. Pendientes / Backlog

| Feature | Prioridad | Estado |
|---|---|---|
| Agente autónomo — fix documento | Alta | 🔄 En debugging |
| Outlook OAuth2 | Media | ⏳ Pendiente |
| Atajos de teclado | Media | ⏳ Pendiente |
| Responsive mobile | Media | ⏳ Pendiente |
| Calendario (Google Calendar) | Media | ⏳ Pendiente |
| Empaquetado Electron/Tauri | Baja | ⏳ Fase futura |
| Voz mejorada (Whisper local) | Baja | ⏳ Fase futura |
| Agente con más herramientas | Baja | ⏳ Fase futura |

---

## 12. Notas Técnicas Importantes

- `API_URL = ""` en todos los archivos frontend (rutas relativas via Nginx)
- Streaming usa `json.dumps/json.loads` para preservar espacios y saltos de línea
- ChromaDB telemetry errors (`capture() takes 1 positional argument`) son inofensivos
- El modelo de embeddings tarda ~30s en cargar al primer arranque tras reinicio
- `restart: unless-stopped` en todos los contenedores + `systemctl enable docker`
- Ruta `/conversations/search` debe ir ANTES de `/conversations/{id}` en FastAPI
- Sandbox ejecuta código via `docker run --rm --network none` pasando código por `-c`
- Tailscale interfaz `tailscale0` debe estar en zona `trusted` del firewall RHEL
- Nginx `server_name _` acepta cualquier hostname — necesario para acceso por IP Tailscale
- Email Outlook bloqueado: Microsoft eliminó auth básica IMAP para @outlook.com/@hotmail.com

---

## 13. Próximos Pasos al Retomar

1. **Verificar fix del agente** — probar si el último `service.py` resuelve el error de `'content'`
2. **Completar agente** — una vez funcionando, agregar más herramientas (escribir emails, crear tareas)
3. **Atajos de teclado** — `Ctrl+K` para buscar, `Ctrl+N` nueva conversación, etc.
4. **Responsive mobile** — adaptar layout para pantallas pequeñas
5. **Calendario** — integración Google Calendar
6. **Empaquetado Electron** — cuando las features estén completas

---

*Checkpoint generado por MATE · Motor de Asistencia Técnica e Inteligencia by JJRM*