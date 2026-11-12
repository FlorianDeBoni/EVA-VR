from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


class DetailCategory(StrEnum):
    """What kind of detail a `Detail` is."""

    FURNITURE = "furniture"
    SHAPE = "shape"
    MATERIAL = "material"
    COLOR = "color"
    LIGHTING = "lighting"
    ACCESSORY = "accessory"


@dataclass(frozen=True)
class Detail:
    """One design decision about the room: a piece of furniture, a shape, a material…

    `space` is the name of a space of the validated spatial design, or None when the detail
    applies to the whole room (a color palette, a material used everywhere).
    """

    name: str
    category: DetailCategory
    description: str
    space: str | None = None
    quantity: int | None = None


@dataclass(frozen=True)
class DetailedDesign:
    """The details of the room: what the last step is about.

    Kept in the graph state; the database holds the working draft and, once the user
    accepted it, the validated copy. The step ends with a picture: `latest_image_version` is
    the latest picture generated in this step (a version of `concept_images`), and
    `is_validated` means the user accepted the details together with a picture: the final one.
    """

    details: list[Detail]
    is_validated: bool
    latest_image_version: int | None = None


class DetailInput(BaseModel):
    """One detail, as the agent writes it."""

    name: str = Field(min_length=1, description="Short name, e.g. 'Round oak table'")
    category: DetailCategory = Field(description="Kind of detail")
    description: str = Field(
        min_length=1,
        description="What it is and why the task needs it: shape, material, color, size…",
    )
    space: str | None = Field(
        default=None,
        description="Name of the space it belongs to; leave out when it applies to the whole room",
    )
    quantity: int | None = Field(default=None, ge=1, description="How many, for furniture")


class UpdateDetailedDesignInput(BaseModel):
    """Arguments of the `update_detailed_design` tool."""

    details: list[DetailInput] = Field(
        description="The complete, up-to-date list of details (replaces the old list)"
    )
    # Injected by the graph, hidden from the model.
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]


class ValidateDetailedDesignInput(BaseModel):
    """Arguments of the `validate_detailed_design` tool."""

    version: int | None = Field(
        default=None, ge=1, description="Picture version the user accepted. Default: the latest"
    )
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
