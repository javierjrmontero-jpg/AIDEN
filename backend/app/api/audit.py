from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("/audit")
async def get_audit_log(
    limit: int = Query(default=50, le=200),
    source: str | None = Query(default=None, description="chat | agent"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Devuelve el historial de acciones ejecutadas por el asistente."""
    q = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.timestamp))
    )
    if source in ("chat", "agent"):
        q = q.where(AuditLog.source == source)
    q = q.limit(limit)

    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id":             log.id,
            "timestamp":      log.timestamp.isoformat() if log.timestamp else None,
            "source":         log.source,
            "tool_name":      log.tool_name,
            "parameters":     log.parameters,
            "result_summary": log.result_summary,
            "status":         log.status,
        }
        for log in logs
    ]
