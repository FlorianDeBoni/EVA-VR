from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ConceptDesign:
    """Progress of the concept design step, kept in the graph state.

    The images themselves stay in the database.
    """

    reference_count: int
    latest_version: int | None
    is_validated: bool
    # Changes whenever the references are replaced by a new search (None while there are none).
    references_revision: int | None = None


@dataclass(frozen=True)
class ReferenceImage:
    """One web image shown to the user as 'Reference <position>'."""

    position: int
    image_b64: str
    mime_type: str
    title: str
    source_url: str
    page_url: str


@dataclass(frozen=True)
class ConceptImage:
    """One AI-generated concept image."""

    version: int
    image_b64: str
    mime_type: str
    prompt: str


class GenerateConceptImageInput(BaseModel):
    """Arguments of the `generate_concept_image` tool."""

    prompt: str = Field(
        min_length=1,
        description=(
            "Complete description of the OVERALL design to draw (volume, spatial layout, mood, "
            "palette, materials, light). When iterating, say what to change and what to keep."
        ),
    )
    reference_numbers: list[int] = Field(
        default_factory=list,
        description="Numbers (1-3) of the reference images to draw elements from",
    )
    base_version: int | None = Field(
        default=None,
        ge=1,
        description="Concept version to iterate on. Default: the latest one",
    )
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]


class ValidateConceptInput(BaseModel):
    """Arguments of the `validate_concept` tool."""

    version: int | None = Field(
        default=None, ge=1, description="Concept version the user accepted. Default: the latest"
    )
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
