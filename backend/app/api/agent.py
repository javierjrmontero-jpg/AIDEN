from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.agent.service import run_agent

router = APIRouter()

class AgentRequest(BaseModel):
    task: str

@router.post("/agent/run")
async def run_agent_endpoint(
    request: AgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return StreamingResponse(
        run_agent(request.task, current_user, db),
        media_type="text/event-stream"
    )