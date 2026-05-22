from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.models.user import User
from app.services.sandbox.service import execute_code
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

FORBIDDEN_PATTERNS = {
    "python": ["import os", "import sys", "import subprocess", "__import__",
               "open(", "exec(", "eval(", "compile(", "importlib"],
    "bash": ["rm -rf", "mkfs", "dd if=", "> /dev/", "chmod 777",
             "wget ", "curl ", "nc ", "ncat "],
    "javascript": ["require('fs')", "require(\"fs\")", "process.exit",
                   "child_process", "require('child"]
}

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"

@router.post("/sandbox/execute")
async def execute_code_endpoint(
    request: ExecuteRequest,
    current_user: User = Depends(get_current_user)
):
    if len(request.code) > 10000:
        raise HTTPException(400, "Código demasiado largo. Máximo 10.000 caracteres.")

    language = request.language.lower()
    patterns = FORBIDDEN_PATTERNS.get(language, [])
    code_lower = request.code.lower()

    for pattern in patterns:
        if pattern.lower() in code_lower:
            raise HTTPException(400, f"Operación no permitida en sandbox: {pattern}")

    result = await execute_code(request.code, language)
    return result