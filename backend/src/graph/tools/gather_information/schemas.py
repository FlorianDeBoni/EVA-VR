from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class InformationToGather:
    """
    This class is used to define the information that needs to be gathered from the user.

    The first four fields are None until the user has answered them.
    """

    user_type: str | None
    number_of_users: int | None

    task_description: str | None
    goal: str | None

    must_have_features: list[str]

    is_validated: bool


class UpdateInformationInput(BaseModel):
    """Arguments of the `update_information` tool. Only the fields that changed are sent."""

    user_type: str | None = Field(
        default=None, description="Who will use the room, e.g. 'a team of architects'"
    )
    number_of_users: int | None = Field(
        default=None, ge=1, description="How many people use the room at the same time"
    )
    task_description: str | None = Field(
        default=None, description="The creative task that will be done inside the room"
    )
    goal: str | None = Field(default=None, description="The overall goal of that task")
    must_have_features: list[str] | None = Field(
        default=None,
        description="The complete, up-to-date list of must-have features (replaces the old list)",
    )
    # Injected by the graph, hidden from the model.
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]


class ValidateInformationInput(BaseModel):
    """Arguments of the `validate_information` tool: none for the model, only injected ones."""

    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]
