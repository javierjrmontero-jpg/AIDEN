from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, conversations
from app.core.config import settings
from app.core.database import init_db

app = FastAPI(
    title="AIDEN",
    description="Artificial Intelligence Driven ENvironment",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(chat.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"status": "online", "assistant": settings.ASSISTANT_NAME}

@app.get("/health")
async def health():
    return {"status": "healthy"}
