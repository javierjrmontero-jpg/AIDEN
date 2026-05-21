from sqlalchemy import Column, String, Text, DateTime, Float
from app.models.conversation import Base
from datetime import datetime
import uuid

class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(50), default="general")
    importance = Column(Float, default=0.5)
    source_conversation_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
