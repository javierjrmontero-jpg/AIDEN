from sqlalchemy import Column, String, Boolean, DateTime
from app.models.conversation import Base
from datetime import datetime
import uuid


class CalendarConfig(Base):
    __tablename__ = "calendar_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String(50), nullable=False, default="google")
    google_email = Column(String(200), nullable=True)
    refresh_token = Column(String(500), nullable=False)
    # Qué cliente OAuth emitió el token: "web" (botón dentro de MATE) o
    # "desktop" (script de administración). Un refresh_token solo se canjea
    # con el mismo par de credenciales que lo emitió.
    client_kind = Column(String(20), nullable=False, default="web")
    calendar_id = Column(String(200), nullable=False, default="primary")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
