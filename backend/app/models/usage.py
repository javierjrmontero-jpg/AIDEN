from sqlalchemy import Column, String, Integer, DateTime, Float
from app.models.conversation import Base
from datetime import datetime
import uuid

class SearchUsage(Base):
    __tablename__ = "search_usage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    query = Column(String(500), nullable=False)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
