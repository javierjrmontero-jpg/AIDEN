import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    db: AsyncSession,
    user_id: str,
    source: str,
    tool_name: str,
    parameters: dict,
    result: str,
    status: str = "success",
) -> None:
    """Escribe una entrada en el audit log. Silencia errores para no afectar el flujo."""
    try:
        params_str = json.dumps(parameters, ensure_ascii=False, default=str)
        entry = AuditLog(
            user_id=user_id,
            source=source,
            tool_name=tool_name,
            parameters=params_str[:2000],
            result_summary=(result or "")[:500],
            status=status,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        logger.error(f"[audit] Error escribiendo entrada: {e}")
