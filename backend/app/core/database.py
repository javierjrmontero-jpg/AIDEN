from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.conversation import Base
import os

# Registrar modelos adicionales para que Base.metadata.create_all los incluya
import app.models.audit_log        # noqa: F401
import app.models.autonomous_rule   # noqa: F401
import app.models.user_settings     # noqa: F401

# Asegurar prefijo async para SQLite
DATABASE_URL = "sqlite+aiosqlite:////data/db/aiden.db"

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    os.makedirs("/data/db", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
