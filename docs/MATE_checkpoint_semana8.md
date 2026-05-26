# MATE — Checkpoint Ejecutivo
**Fecha:** 26/05/2026  
**Versión:** Semana 8  
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
| Repo GitHub | https://github.com/javierjrmontero-jpg/AIDEN.git |
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

# Commit y push (SIEMPRE los dos juntos)
cd ~/aiden && git add . && git commit -m "mensaje" && git push origin main

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
│   │   │   └── agent/     # service.py — agente autónomo 7 herramientas
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
│   ├── nginx.conf
│   └── certs/
├── data/
│   ├── db/aiden.db
│   ├── vectordb/
│   └── models/
├── scripts/
│   └── backup.sh
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
- ✅ Separación de roles admin/usuario (is_admin)

### IA y Conocimiento
- ✅ RAG sobre documentos (PDF/DOCX/TXT/MD)
- ✅ OCR automático para PDFs escaneados (Tesseract)
- ✅ Memoria persistente entre conversaciones
- ✅ Búsqueda web automática con Brave Search API
- ✅ Indicador visual "Buscando en la web..."
- ✅ Multiidioma (es/en/pt/fr/de/it) desde perfil

### Agente Autónomo
- ✅ Arquitectura dos fases (investigación → documento)
- ✅ 7 herramientas: web_search, execute_python, execute_bash,
     search_documents, read_memories, create_task, send_email
- ✅ Documento final forzado con tool_choice
- ✅ Descarga del documento generado

### Productividad
- ✅ Tareas y recordatorios con prioridad y fecha límite
- ✅ Alertas de tareas vencidas (cada 5 minutos)
- ✅ Email multi-cuenta Gmail (IMAP/SMTP)
- ✅ Estadísticas personales con gráfico de actividad

### Código
- ✅ Sandbox Docker aislado Python / JavaScript / Bash
- ✅ Botón ▶ Ejecutar en cada bloque de código

### UI/UX
- ✅ Markdown con syntax highlighting
- ✅ Botones copiar/descargar en respuestas
- ✅ Sidebar con búsqueda y navegación
- ✅ Sistema de notificaciones animadas
- ✅ Voz STT (micrófono) y TTS (texto→voz)
- ✅ Atajos de teclado: Ctrl+M (nueva conv), Ctrl+K (buscar), Ctrl+B (sidebar), Escape
- ✅ Responsive mobile: sidebar como overlay, backdrop, cierre automático

### Infraestructura
- ✅ Nginx reverse proxy HTTPS
- ✅ Certificado autofirmado mate.local
- ✅ Tailscale VPN para acceso remoto
- ✅ Arranque automático Docker al reiniciar VM
- ✅ Backup automático diario 2AM + manual desde admin
- ✅ Panel de administración completo

---

## 7. Decisiones Arquitectónicas

| Decisión | Elección | Motivo |
|---|---|---|
| Base de datos | SQLite | Simplicidad, sin dependencias |
| Vector DB | ChromaDB | Local, privacy-first |
| LLM | Claude claude-sonnet-4-5 | Calidad y API confiable |
| Búsqueda web | Brave Search | Privacidad, USD 5/mes |
| Proxy | Nginx | Estándar, liviano |
| Contenedores | Docker Compose | Portabilidad |
| Acceso remoto | Tailscale | Sin configurar router |
| App futura | Electron/Tauri | Empaquetar Next.js existente |
| Email Outlook | Pendiente OAuth2 | Microsoft bloqueó auth básica |
| Atajo nueva conv | Ctrl+M | Ctrl+N y Ctrl+Shift+N ocupados por browser |

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

## 10. Notas Técnicas Importantes

- `API_URL = ""` en frontend (rutas relativas via Nginx)
- Streaming usa `json.dumps/json.loads` para preservar espacios
- ChromaDB telemetry errors son inofensivos
- Embeddings tardan ~30s al primer arranque
- `restart: unless-stopped` en todos los contenedores
- Ruta `/conversations/search` debe ir ANTES de `/conversations/{id}`
- Sandbox: `docker run --rm --network none`
- Tailscale interfaz `tailscale0` en zona `trusted` del firewall
- `newConversation` debe ser `useCallback` y definirse ANTES del useEffect de shortcuts
- SIEMPRE hacer `git push origin main` después de cada commit

---

## 11. Pendientes / Backlog

| Feature | Prioridad | Estado |
|---|---|---|
| Calendario (Google Calendar) | Media | ⏳ Siguiente |
| Outlook OAuth2 | Media | ⏳ Pendiente |
| Empaquetado Electron/Tauri | Baja | ⏳ Fase futura |
| Voz mejorada (Whisper local) | Baja | ⏳ Fase futura |
| Agente — más herramientas futuras | Baja | ⏳ Fase futura |

---

## 12. Próximos Pasos al Retomar

1. **Google Calendar** — ver/crear eventos desde MATE
2. **Outlook OAuth2** — desbloquear email Outlook/Hotmail
3. **Empaquetado Electron** — cuando las features estén completas

---

## 13. Próximo Prompt Recomendado

```
Retomamos el proyecto MATE (Motor de Asistencia Técnica e Inteligencia).
Te adjunto el checkpoint actualizado con el estado completo del proyecto.
El próximo paso es integrar Google Calendar: ver eventos próximos y crear
eventos desde el chat y desde el agente autónomo.
Stack: FastAPI + Next.js + SQLite + Docker en RHEL 10, repo en ~/aiden.
Recordá siempre hacer git push origin main después de cada commit.
```

---

*Checkpoint generado por MATE · Motor de Asistencia Técnica e Inteligencia by JJRM*
