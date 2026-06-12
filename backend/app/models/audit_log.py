from sqlalchemy import Column, String, Text, DateTime
from app.models.conversation import Base
from datetime import datetime
import uuid


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     = Column(String, nullable=False, index=True)
    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)
    source      = Column(String(10), nullable=False)   # "chat" | "agent"
    tool_name   = Column(String(60), nullable=False)
    parameters  = Column(Text, nullable=True)          # JSON truncado a 2000 chars
    result_summary = Column(Text, nullable=True)       # primeros 500 chars del result
    status      = Column(String(10), nullable=False, default="success")  # "success"|"error"
