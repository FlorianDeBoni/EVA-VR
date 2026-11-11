import os
from enum import StrEnum


class EnvKeyName(StrEnum):
    """Enum for environment variable keys."""

    KEY_API_PORT = "API_PORT"
    KEY_OPENAI_API_KEY = "OPENAI_API_KEY"
    KEY_OPENAI_IMAGE_MODEL = "OPENAI_IMAGE_MODEL"
    KEY_GPT_COMPLETION_MODEL = "GPT_COMPLETION_MODEL"
    KEY_MAX_PAST_IMAGES = "MAX_PAST_IMAGES"
    KEY_DEFAULT_MODEL = "DEFAULT_MODEL"
    KEY_IMAGE_SEARCH_TOP_K = "IMAGE_SEARCH_TOP_K"
    KEY_IMAGE_RANK_BATCH_SIZE = "IMAGE_RANK_BATCH_SIZE"
    KEY_KEYWORD_WEIGHT = "KEYWORD_WEIGHT"
    KEY_CATEGORY_WEIGHT = "CATEGORY_WEIGHT"
    KEY_BLOCKED_HOSTS = "BLOCKED_HOSTS"
    KEY_OPENAI_STT_MODEL = "OPENAI_STT_MODEL"
    KEY_STT_MAX_AUDIO_BYTES = "STT_MAX_AUDIO_BYTES"
    KEY_LOG_LEVEL = "LOG_LEVEL"
    KEY_LOG_FORMAT = "LOG_FORMAT"


class EnvManager:
    """Class to manage environment variables."""

    @staticmethod
    def get_env_variable(key: EnvKeyName, default: str | None = None) -> str:
        """Get the value of an environment variable.

        Args:
            key (EnvKeyName): The key of the environment variable.
            default (str | None): Returned when the variable is not set.

        Returns:
            str: The value of the environment variable.

        Raises:
            KeyError: If the environment variable is not found and no default is given.
        """

        value = os.getenv(key.value)
        if value is None:
            if default is not None:
                return default
            raise KeyError(f"Environment variable '{key.value}' not found.")
        return value
