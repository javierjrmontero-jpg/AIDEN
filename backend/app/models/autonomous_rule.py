from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from app.models.conversation import Base
from datetime import datetime
import uuid


class AutonomousRule(Base):
    __tablename__ = "autonomous_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(200), nullable=False)

    # Condición: qué evaluar
    # Tipos: unread_gt | overdue_tasks_gt | due_today_gt | followups_pending
    condition_type = Column(String(50), nullable=False)
    condition_params = Column(Text, default="{}")   # JSON: {"threshold": N}

    # Acción: qué hacer si se cumple la condición
    # Tipos: tts | notify | create_task
    action_type = Column(String(50), nullable=False)
    action_params = Column(Text, default="{}")      # JSON: {"message": "...", "title": "..."}

    enabled = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=60)  # evitar spam
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
