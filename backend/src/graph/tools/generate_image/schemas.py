from dataclasses import dataclass

from pydantic import BaseModel, Field


class ImageGenerationError(RuntimeError):
    """The model answered without an image."""


@dataclass(frozen=True)
class GeneratedImage:
    """Raw image bytes with their MIME type."""

    data: bytes
    mime_type: str


class GenerateImageInput(BaseModel):
    """Arguments the agent provides when calling the tool."""

    prompt: str = Field(
        min_length=1,
        description="Description of the image to generate, e.g. 'a brutalist library at dusk'",
    )
