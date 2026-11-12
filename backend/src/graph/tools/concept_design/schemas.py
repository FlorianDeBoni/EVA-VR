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


class ValidateConceptInput(BaseModel):
    """Arguments of the `validate_concept` tool."""

    version: int | None = Field(
        default=None, ge=1, description="Concept version the user accepted. Default: the latest"
    )
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
