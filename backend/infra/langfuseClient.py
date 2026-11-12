from langfuse import Langfuse

from backend.src.settings.envManager import EnvKeyName, EnvManager


class LangfuseClient:
    """Lazily creates and caches a Langfuse client."""

    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host
        self._client: Langfuse | None = None

    @classmethod
    def from_env(cls) -> LangfuseClient:
        """Build from LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (see .env.backend)."""
        return cls(
            public_key=EnvManager.get_env_variable(EnvKeyName.KEY_LANGFUSE_PUBLIC_KEY),
            secret_key=EnvManager.get_env_variable(EnvKeyName.KEY_LANGFUSE_SECRET_KEY),
            host=EnvManager.get_env_variable(EnvKeyName.KEY_LANGFUSE_HOST),
        )

    def get_client(self) -> Langfuse:
        """Return the (lazily created, cached) client."""
        if self._client is None:
            self._client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
        return self._client
