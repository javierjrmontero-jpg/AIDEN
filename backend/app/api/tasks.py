from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from datetime import datetime
import uuid

router = APIRouter()

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    due_date: Optional[str] = None
    priority: Optional[str] = "medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None

@router.get("/tasks")
async def list_tasks(
    completed: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Task).where(Task.user_id == current_user.id)
    if completed is not None:
        query = query.where(Task.completed == completed)
    query = query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [format_task(t) for t in tasks]

@router.post("/tasks")
async def create_task(
    request: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    due_date = None
    if request.due_date:
        try:
            due_date = datetime.fromisoformat(request.due_date)
        except Exception:
            pass

    task = Task(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=request.title,
        description=request.description or "",
        due_date=due_date,
        priority=request.priority or "medium",
        completed=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(task)
    await db.commit()
    return format_task(task)

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    request: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .where(Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Tarea no encontrada")

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.priority is not None:
        task.priority = request.priority
    if request.completed is not None:
        task.completed = request.completed
    if request.due_date is not None:
        try:
            task.due_date = datetime.fromisoformat(request.due_date)
        except Exception:
            pass

    task.updated_at = datetime.utcnow()
    await db.commit()
    return format_task(task)

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .where(Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    await db.delete(task)
    await db.commit()
    return {"status": "deleted"}

def format_task(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description or "",
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "priority": t.priority,
        "completed": t.completed,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat()
    }