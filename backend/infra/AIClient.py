from typing import Any

from openai import OpenAI

from backend.src.settings.envManager import EnvKeyName, EnvManager


class AIClient:
    """Lazily creates and caches an OpenAI client."""

    def __init__(self, api_key: str, **options: Any) -> None:
        self._api_key = api_key
        self._options = options
        self._client: OpenAI | None = None

    @classmethod
    def from_env(cls) -> AIClient:
        """Build from OPENAI_API_KEY (see .env.backend)."""
        return cls(EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY))

    def get_client(self) -> OpenAI:
        """Return the (lazily created, cached) client."""
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key, **self._options)
        return self._client
