from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, conversations, auth, documents, generate, memories, sandbox, admin, tasks, email, stats, agent, calendar, voice, audit, briefing, briefing_weekly, tasks_prioritize, email_followup, autonomous_rules, context_extract, user_settings, domotica, webhook
from app.core.config import settings
from app.core.database import init_db


app = FastAPI(
    title="MATE",
    description="Motor de Asistencia Técnica e Inteligencia — by JJRM",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mate.local",
        "http://mate.local",
        "http://mate.local:3000",
        "http://localhost:3000",
        "https://molmont.duckdns.org:8443",
        "https://molmont.duckdns.org"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(memories.router, prefix="/api/v1")
app.include_router(sandbox.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(briefing.router, prefix="/api/v1")
app.include_router(briefing_weekly.router, prefix="/api/v1")
app.include_router(tasks_prioritize.router, prefix="/api/v1")
app.include_router(email_followup.router, prefix="/api/v1")
app.include_router(autonomous_rules.router, prefix="/api/v1")
app.include_router(context_extract.router, prefix="/api/v1")
app.include_router(user_settings.router, prefix="/api/v1")
app.include_router(domotica.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"status": "online", "assistant": "MATE", "author": "JJRM"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
