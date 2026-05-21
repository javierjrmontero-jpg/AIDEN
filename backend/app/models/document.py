from sqlalchemy import Column, String, DateTime, Integer, Text
from app.models.conversation import Base
from datetime import datetime
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String(300), nullable=False)
    file_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)
