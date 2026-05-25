from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, conversations, auth, documents, generate, memories, sandbox, admin, tasks, email
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
        "http://localhost:3000"
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

@app.get("/")
async def root():
    return {"status": "online", "assistant": "MATE", "author": "JJRM"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
