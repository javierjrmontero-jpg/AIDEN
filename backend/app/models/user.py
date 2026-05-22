from sqlalchemy import Column, String, Boolean, DateTime, Text
from app.models.conversation import Base
from datetime import datetime
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(200), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Perfil
    role = Column(String(200), nullable=True)
    context = Column(Text, nullable=True)
    preferences = Column(Text, nullable=True)
    language = Column(String(10), default="es")
