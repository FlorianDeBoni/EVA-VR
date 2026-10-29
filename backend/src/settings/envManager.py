import os
from enum import StrEnum


class EnvKeyName(StrEnum):
    """Enum for environment variable keys."""

    KEY_GEMINI_KEY = "GEMINI_KEY"
    KEY_SERPAPI_KEY = "SERPAPI_KEY"
    KEY_API_PORT = "API_PORT"


class EnvManager:
    """Class to manage environment variables."""

    @staticmethod
    def get_env_variable(key: EnvKeyName) -> str:
        """Get the value of an environment variable.

        Args:
            key (EnvKeyName): The key of the environment variable.

        Returns:
            str: The value of the environment variable.

        Raises:
            KeyError: If the environment variable is not found.
        """

        value = os.getenv(key.value)
        if value is None:
            raise KeyError(f"Environment variable '{key.value}' not found.")
        return value
