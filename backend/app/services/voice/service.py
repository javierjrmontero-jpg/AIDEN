"""
Transcripción de voz local con faster-whisper (CPU).

El modelo se carga de forma perezosa la primera vez y se reutiliza.
La descarga se cachea en /root/.cache/huggingface (mapeado a data/models),
igual que el modelo de embeddings. La transcripción es CPU-bound, por eso
se ejecuta en un thread aparte para no bloquear el event loop.
"""

import asyncio
import logging
import os
import tempfile

from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        logger.info(f"Cargando modelo Whisper '{settings.WHISPER_MODEL}' (puede tardar la 1ra vez)...")
        _model = WhisperModel(
            settings.WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Modelo Whisper cargado.")
    return _model


def _transcribe_sync(audio_path: str, language: str) -> str:
    model = _get_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language or None,
        beam_size=1,            # rápido; subir a 5 mejora calidad pero es más lento
        vad_filter=False,       # se puede activar para recortar silencios
    )
    return " ".join(seg.text for seg in segments).strip()


async def transcribe_audio(audio_bytes: bytes, language: str = "es") -> str:
    # Escribir a archivo temporal; faster-whisper decodifica con PyAV
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        return await asyncio.to_thread(_transcribe_sync, path, language)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
