from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
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
        description=(
            "Complete description of the whole picture to draw. When iterating, say what to "
            "change and what to keep."
        ),
    )
    reference_numbers: list[int] = Field(
        default_factory=list,
        description="Numbers (1-3) of the web reference images to draw elements from (step 2)",
    )
    base_version: int | None = Field(
        default=None,
        ge=1,
        description="Version to iterate on. Default: the latest one of the current step",
    )
    # Injected by the graph, hidden from the model.
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
