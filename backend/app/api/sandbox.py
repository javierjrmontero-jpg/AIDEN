from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.models.user import User
from app.services.sandbox.service import execute_python
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ExecuteRequest(BaseModel):
    code: str

@router.post("/sandbox/execute")
async def execute_code(
    request: ExecuteRequest,
    current_user: User = Depends(get_current_user)
):
    if len(request.code) > 10000:
        raise HTTPException(400, "Código demasiado largo. Máximo 10.000 caracteres.")

    # Validaciones básicas de seguridad
    forbidden = ["import os", "import sys", "import subprocess", "__import__",
                 "open(", "exec(", "eval(", "compile(", "importlib"]
    code_lower = request.code.lower()
    for pattern in forbidden:
        if pattern.lower() in code_lower:
            raise HTTPException(400, f"Operación no permitida en sandbox: {pattern}")

    result = await execute_python(request.code)
    return result
