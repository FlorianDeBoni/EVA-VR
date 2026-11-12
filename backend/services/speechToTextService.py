from functools import lru_cache

from openai import OpenAI

from backend.infra.AIClient import AIClient
from backend.services.errors import SpeechToTextError
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class SpeechToTextService:
    """Transcribes audio with OpenAI.

        text = get_speech_to_text_service().transcribe(audio_bytes, "voice.webm")

    Model, size limit and language come from .env.backend (OPENAI_STT_MODEL,
    STT_MAX_AUDIO_BYTES, STT_LANGUAGE) unless passed explicitly. The OpenAI client is
    created lazily and cached.
    """

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        max_audio_bytes: int | None = None,
        language: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._max_audio_bytes = max_audio_bytes
        self._language = language
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = AIClient.from_env().get_client()
        return self._client

    @property
    def model(self) -> str:
        return self._model or EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_STT_MODEL)

    @property
    def max_audio_bytes(self) -> int:
        if self._max_audio_bytes is not None:
            return self._max_audio_bytes
        return int(EnvManager.get_env_variable(EnvKeyName.KEY_STT_MAX_AUDIO_BYTES))

    @property
    def language(self) -> str:
        return self._language or EnvManager.get_env_variable(EnvKeyName.KEY_STT_LANGUAGE)

    def transcribe(
        self,
        audio: bytes,
        filename: str,
        content_type: str | None = None,
        language: str | None = None,
        prompt: str | None = None,
    ) -> str:
        """Return the transcript of `audio`.

        Args:
            audio: Raw audio bytes (flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav or webm).
            filename: Original file name; OpenAI uses its extension to detect the format.
            content_type: MIME type of the upload, if known.
            language: ISO-639-1 code of the speech; defaults to STT_LANGUAGE ("en").
            prompt: Optional text hinting at vocabulary or style.

        Raises:
            SpeechToTextError: If the audio is empty or larger than the limit.
        """
        if not audio:
            raise SpeechToTextError("audio is empty")
        if len(audio) > self.max_audio_bytes:
            raise SpeechToTextError(f"audio exceeds {self.max_audio_bytes} bytes")

        self.logger.info("Transcribing %s (%d bytes)", filename, len(audio))
        options = {
            k: v for k, v in {"language": language or self.language, "prompt": prompt}.items() if v
        }
        file = (filename, audio, content_type) if content_type else (filename, audio)
        resp = self.client.audio.transcriptions.create(model=self.model, file=file, **options)
        return resp.text


@lru_cache(maxsize=1)
def get_speech_to_text_service() -> SpeechToTextService:
    """Shared default service instance."""
    return SpeechToTextService()
