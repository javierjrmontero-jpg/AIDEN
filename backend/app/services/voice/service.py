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


# Whisper alucina sobre audio sin voz: ante silencio o ruido ambiente devuelve
# frases inventadas, casi siempre estas. Se descartan por si alguna se cuela.
_ALUCINACIONES = (
    "subtítulos realizados por",
    "subtitulado por",
    "gracias por ver el video",
    "gracias por ver este video",
    "más videos en",
    "amara.org",
)


def _transcribe_sync(audio_path: str, language: str) -> str:
    model = _get_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language or None,
        beam_size=5,                      # greedy (1) degrada bastante en español
        vad_filter=True,                  # recorta lo que no es voz antes de decodificar
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,  # evita que se realimente su propia alucinación
        no_speech_threshold=0.6,
    )

    texto = " ".join(seg.text for seg in segments).strip()

    normalizado = texto.lower()
    if any(frase in normalizado for frase in _ALUCINACIONES):
        logger.info(f"Descartada transcripción alucinada: {texto!r}")
        return ""
    return texto


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
