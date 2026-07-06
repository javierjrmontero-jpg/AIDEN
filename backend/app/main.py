from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api import chat, conversations, auth, documents, generate, memories, sandbox, admin, tasks, email, stats, agent, calendar, voice, audit, briefing, briefing_weekly, tasks_prioritize, email_followup, autonomous_rules, context_extract, user_settings, domotica, webhook
from app.core.config import settings
from app.core.database import init_db

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MATE",
    description="Motor de Asistencia Técnica e Inteligencia — by JJRM",
    version="0.1.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mate.local",
        "https://mate.molmont.com.ar",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

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
