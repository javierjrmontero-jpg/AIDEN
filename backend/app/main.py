from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat
from app.core.config import settings

app = FastAPI(
    title="AIDEN",
    description="Artificial Intelligence Driven ENvironment",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://10.10.151.147:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"status": "online", "assistant": settings.ASSISTANT_NAME}

@app.get("/health")
async def health():
    return {"status": "healthy"}
