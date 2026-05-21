from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.llm.client import client
from app.core.config import settings
import io
import re

router = APIRouter()

class GenerateRequest(BaseModel):
    content: str
    format: str = "md"
    filename: str = "documento"

@router.post("/generate/document")
async def generate_document(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user)
):
    content = request.content
    filename = request.filename.replace(" ", "_")

    if request.format == "md":
        file_bytes = content.encode("utf-8")
        media_type = "text/markdown"
        filename = f"{filename}.md"

    elif request.format == "txt":
        # Limpiar markdown para texto plano
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        clean = re.sub(r'\*(.*?)\*', r'\1', clean)
        clean = re.sub(r'#{1,6}\s', '', clean)
        clean = re.sub(r'`(.*?)`', r'\1', clean)
        file_bytes = clean.encode("utf-8")
        media_type = "text/plain"
        filename = f"{filename}.txt"

    elif request.format == "html":
        # Conversión básica de Markdown a HTML
        html_content = content
        html_content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html_content)
        html_content = re.sub(r'\n', '<br>\n', html_content)

        full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{filename}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #333; }}
  h1, h2, h3 {{ color: #1a1a2e; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
  pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  footer {{ margin-top: 40px; color: #999; font-size: 0.8em; text-align: center; }}
</style>
</head>
<body>
{html_content}
<footer>Generado por MATE — Motor de Asistencia Técnica e Inteligencia by JJRM</footer>
</body>
</html>"""
        file_bytes = full_html.encode("utf-8")
        media_type = "text/html"
        filename = f"{filename}.html"

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
