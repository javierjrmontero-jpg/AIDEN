from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db, AsyncSessionLocal
from app.core.auth import get_current_user
from app.models.user import User
from app.models.document import Document
from app.services.rag.service import extract_text, index_document, delete_document_chunks
import asyncio
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {"pdf", "txt", "docx", "md"}
MAX_SIZE = 50 * 1024 * 1024

@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "size_bytes": d.size_bytes,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "created_at": d.created_at.isoformat()
        }
        for d in docs
    ]

async def _process_document_bg(doc_id: str, user_id: str, filename: str, ext: str, content: bytes):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return
        try:
            logger.info(f"[bg] Extrayendo texto de {filename} ({ext})")
            text = await asyncio.to_thread(extract_text, content, ext)
            if not text.strip():
                raise ValueError("El archivo no contiene texto extraíble")
            chunk_count = await asyncio.to_thread(index_document, user_id, doc_id, filename, text)
            logger.info(f"[bg] Indexados {chunk_count} chunks para {filename}")
            doc.chunk_count = chunk_count
            doc.status = "ready"
        except Exception as e:
            logger.error(f"[bg] Error procesando {filename}: {e}", exc_info=True)
            doc.status = "error"
        await db.commit()


@router.post("/documents")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, f"Tipo no soportado. Permitidos: {ALLOWED_TYPES}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "Archivo demasiado grande. Máximo 50 MB")

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        file_type=ext,
        size_bytes=len(content),
        status="processing",
        created_at=datetime.utcnow()
    )
    db.add(doc)
    await db.commit()

    background_tasks.add_task(_process_document_bg, doc_id, current_user.id, file.filename, ext, content)

    return {"id": doc_id, "filename": file.filename, "chunks": 0, "status": "processing"}

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document)
        .where(Document.id == doc_id)
        .where(Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    delete_document_chunks(current_user.id, doc_id)
    await db.execute(delete(Document).where(Document.id == doc_id))
    await db.commit()
    return {"status": "deleted"}
