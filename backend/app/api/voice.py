from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.core.auth import get_current_user
from app.models.user import User
from app.services.voice.service import transcribe_audio

router = APIRouter()


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("es"),
    current_user: User = Depends(get_current_user),
):
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "Audio vacío")

    # Whisper usa códigos ISO 639-1 ('es'), no BCP-47 ('es-AR')
    lang = (language or "es")[:2]

    try:
        text = await transcribe_audio(audio, lang)
    except Exception as ex:
        raise HTTPException(500, f"Error al transcribir: {ex}")

    return {"text": text}
