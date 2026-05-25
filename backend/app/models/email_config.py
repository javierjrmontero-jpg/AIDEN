from sqlalchemy import Column, String, Boolean, DateTime, Integer
from app.models.conversation import Base
from datetime import datetime
import uuid

class EmailConfig(Base):
    __tablename__ = "email_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    email_address = Column(String(200), nullable=False)
    app_password = Column(String(500), nullable=False)
    imap_host = Column(String(200), nullable=True)
    imap_port = Column(Integer, default=993)
    smtp_host = Column(String(200), nullable=True)
    smtp_port = Column(Integer, default=587)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)