class SessionNotFoundError(LookupError):
    """No session exists with the given id."""


class SpeechToTextError(ValueError):
    """The audio cannot be sent for transcription (empty or too large)."""


class PromptNotFoundError(LookupError):
    """Langfuse has no prompt with this name under the configured label."""
