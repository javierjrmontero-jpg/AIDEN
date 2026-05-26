from sqlalchemy import Column, String, Text, DateTime, Integer
from app.models.conversation import Base
from datetime import datetime
import uuid

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    steps_total = Column(Integer, default=0)
    steps_done = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
