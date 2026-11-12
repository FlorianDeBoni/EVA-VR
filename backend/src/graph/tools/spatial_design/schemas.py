from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


class RelationType(StrEnum):
    """How two spaces relate to each other."""

    ADJACENT = "adjacent"  # next to each other, with a clear boundary
    OPEN_CONNECTION = "open_connection"  # open to each other, one continuous volume
    VISUAL_LINK = "visual_link"  # people in one can see the other
    SEPARATED = "separated"  # kept apart (noise, privacy, concentration)
    CIRCULATION = "circulation"  # people move from one to the other


@dataclass(frozen=True)
class Space:
    """One space or area of the room."""

    name: str
    purpose: str
    activities: list[str] = field(default_factory=list)
    capacity: int | None = None
    size: str | None = None


@dataclass(frozen=True)
class Relationship:
    """How two spaces (named by `Space.name`) relate and interact."""

    from_space: str
    to_space: str
    type: RelationType
    description: str = ""


@dataclass(frozen=True)
class SpatialDesign:
    """The spatial organization of the room: its spaces and how they relate.

    Kept in the graph state; the database holds the working draft and, once the user
    accepted it, the validated copy. The step ends with a picture of it: `latest_image_version`
    is the latest picture generated in this step (a version of `concept_images`), and
    `is_validated` means the user accepted the organization together with a picture.
    """

    spaces: list[Space]
    relationships: list[Relationship]
    is_validated: bool
    latest_image_version: int | None = None


class SpaceInput(BaseModel):
    """One space, as the agent writes it."""

    name: str = Field(min_length=1, description="Short unique name, e.g. 'Brainstorm area'")
    purpose: str = Field(min_length=1, description="Why this space is needed for the task")
    activities: list[str] = Field(
        default_factory=list, description="What people do there, e.g. ['sketching', 'pitching']"
    )
    capacity: int | None = Field(
        default=None, ge=1, description="How many people use it at the same time"
    )
    size: str | None = Field(
        default=None, description="Relative size, e.g. 'large, the main area' or 'small'"
    )


class RelationshipInput(BaseModel):
    """One relationship between two spaces, as the agent writes it."""

    from_space: str = Field(min_length=1, description="Name of a space of the list")
    to_space: str = Field(min_length=1, description="Name of another space of the list")
    type: RelationType = Field(description="Kind of relationship")
    description: str = Field(default="", description="How these two spaces interact")


class UpdateSpatialDesignInput(BaseModel):
    """Arguments of the `update_spatial_design` tool. Send only what changed."""

    spaces: list[SpaceInput] | None = Field(
        default=None,
        description="The complete, up-to-date list of spaces (replaces the old list)",
    )
    relationships: list[RelationshipInput] | None = Field(
        default=None,
        description="The complete, up-to-date list of relationships (replaces the old list)",
    )
    # Injected by the graph, hidden from the model.
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]


class ValidateSpatialDesignInput(BaseModel):
    """Arguments of the `validate_spatial_design` tool."""

    version: int | None = Field(
        default=None, ge=1, description="Picture version the user accepted. Default: the latest"
    )
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
