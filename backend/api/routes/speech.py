from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import APIError

from backend.api.schemas import TranscriptionResponse
from backend.services.speechToTextService import SpeechToTextError, get_speech_to_text_service

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/transcribe", summary="Transcribe an audio file (OpenAI proxy)")
def transcribe(
    file: Annotated[UploadFile, File(description="Audio file (webm, mp3, wav, m4a, ogg, flac...)")],
    language: Annotated[str | None, Form(description="Optional ISO-639-1 code, e.g. 'fr'")] = None,
    prompt: Annotated[str | None, Form(description="Optional vocabulary/style hint")] = None,
) -> TranscriptionResponse:
    """Forward the audio to OpenAI speech-to-text and return the transcript.

    Sync on purpose: the OpenAI call blocks, so FastAPI runs it in its threadpool.
    """
    try:
        text = get_speech_to_text_service().transcribe(
            file.file.read(),
            file.filename or "audio",
            content_type=file.content_type,
            language=language,
            prompt=prompt,
        )
    except SpeechToTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TranscriptionResponse(text=text)
