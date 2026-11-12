class SessionNotFoundError(LookupError):
    """No session exists with the given id."""


class SpeechToTextError(ValueError):
    """The audio cannot be sent for transcription (empty or too large)."""


class PromptNotFoundError(LookupError):
    """Langfuse has no prompt with this name under the configured label."""


class ConceptImageNotFoundError(LookupError):
    """The session has no concept image with this version."""


class SpatialDesignNotFoundError(LookupError):
    """The session has no spatial design draft to validate."""


class SpatialImageOutdatedError(ValueError):
    """The spatial design was changed after the picture, so the picture no longer shows it."""
