"""
MATE — Reglas Autónomas (F4-4)
GET    /api/v1/rules                     — listar reglas del usuario
POST   /api/v1/rules                     — crear regla
PUT    /api/v1/rules/{rule_id}           — actualizar (nombre, params, enable/disable)
DELETE /api/v1/rules/{rule_id}           — eliminar
PATCH  /api/v1/rules/{rule_id}/triggered — actualiza last_triggered (llamado por el monitor)

Condiciones: unread_gt | overdue_tasks_gt | due_today_gt | followups_pending
Acciones:    tts | notify | create_task
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import json
import uuid

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.autonomous_rule import AutonomousRule

router = APIRouter()

VALID_CONDITIONS = {"unread_gt", "overdue_tasks_gt", "due_today_gt", "followups_pending"}
VALID_ACTIONS    = {"tts", "notify", "create_task"}


def _fmt(r: AutonomousRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "condition_type": r.condition_type,
        "condition_params": json.loads(r.condition_params or "{}"),
        "action_type": r.action_type,
        "action_params": json.loads(r.action_params or "{}"),
        "enabled": r.enabled,
        "cooldown_minutes": r.cooldown_minutes,
        "last_triggered": r.last_triggered.isoformat() if r.last_triggered else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class RuleCreate(BaseModel):
    name: str
    condition_type: str
    condition_params: dict = {}
    action_type: str
    action_params: dict = {}
    cooldown_minutes: int = 60
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    condition_params: Optional[dict] = None
    action_params: Optional[dict] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutonomousRule)
        .where(AutonomousRule.user_id == current_user.id)
        .order_by(AutonomousRule.created_at.asc())
    )
    return [_fmt(r) for r in result.scalars().all()]


@router.post("/rules", status_code=201)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.condition_type not in VALID_CONDITIONS:
        raise HTTPException(400, f"condition_type inválido. Opciones: {VALID_CONDITIONS}")
    if body.action_type not in VALID_ACTIONS:
        raise HTTPException(400, f"action_type inválido. Opciones: {VALID_ACTIONS}")

    rule = AutonomousRule(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=body.name,
        condition_type=body.condition_type,
        condition_params=json.dumps(body.condition_params),
        action_type=body.action_type,
        action_params=json.dumps(body.action_params),
        cooldown_minutes=body.cooldown_minutes,
        enabled=body.enabled,
        created_at=datetime.utcnow(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _fmt(rule)


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutonomousRule)
        .where(AutonomousRule.id == rule_id, AutonomousRule.user_id == current_user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Regla no encontrada")

    if body.name is not None:
        rule.name = body.name
    if body.condition_params is not None:
        rule.condition_params = json.dumps(body.condition_params)
    if body.action_params is not None:
        rule.action_params = json.dumps(body.action_params)
    if body.cooldown_minutes is not None:
        rule.cooldown_minutes = body.cooldown_minutes
    if body.enabled is not None:
        rule.enabled = body.enabled

    await db.commit()
    await db.refresh(rule)
    return _fmt(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutonomousRule)
        .where(AutonomousRule.id == rule_id, AutonomousRule.user_id == current_user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Regla no encontrada")
    await db.delete(rule)
    await db.commit()


@router.patch("/rules/{rule_id}/triggered", status_code=200)
async def mark_triggered(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El monitor llama esto después de ejecutar una acción."""
    result = await db.execute(
        select(AutonomousRule)
        .where(AutonomousRule.id == rule_id, AutonomousRule.user_id == current_user.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Regla no encontrada")
    rule.last_triggered = datetime.utcnow()
    await db.commit()
    return {"status": "ok", "last_triggered": rule.last_triggered.isoformat()}
