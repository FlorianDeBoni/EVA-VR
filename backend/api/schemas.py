from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class HealthStatus(StrEnum):
    """Possible states of the service."""

    OK = "ok"


class HealthResponse(BaseModel):
    """Response body of the health endpoints."""

    status: HealthStatus


class TranscriptionResponse(BaseModel):
    """Transcript returned by the speech-to-text endpoint."""

    text: str


class ChatMessage(BaseModel):
    """One message of the conversation, as sent by the client."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """The conversation so far, for one session."""

    session_id: UUID | None = Field(
        default=None,
        description="Session of the conversation. Created if missing or unknown.",
    )
    messages: list[ChatMessage] = Field(
        description=(
            "Whole history, oldest first. Empty to let the assistant open the conversation; "
            "otherwise it ends with the user's message."
        )
    )

    @model_validator(mode="after")
    def _ends_with_a_user_message(self) -> ChatRequest:
        if self.messages and self.messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return self


class InformationResponse(BaseModel):
    """What the agent has gathered so far (null/empty until the user answered)."""

    user_type: str | None
    number_of_users: int | None
    task_description: str | None
    goal: str | None
    must_have_features: list[str]
    is_validated: bool


class ConceptResponse(BaseModel):
    """Progress of the concept design step. The images are served by the /concept routes."""

    reference_count: int = Field(description="Reference images found: GET .../references/{1..n}")
    latest_version: int | None = Field(description="Latest generated image: GET .../images/{n}")
    is_validated: bool = Field(description="True once the user accepted a concept image")
    references_revision: int | None = Field(
        description="Changes when the references are replaced: use it to refresh their images"
    )


class SpaceResponse(BaseModel):
    """One space of the room."""

    name: str
    purpose: str
    activities: list[str]
    capacity: int | None
    size: str | None


class RelationshipResponse(BaseModel):
    """How two spaces (by name) relate."""

    from_space: str
    to_space: str
    type: str = Field(
        description="adjacent, open_connection, visual_link, separated or circulation"
    )
    description: str


class SpatialDesignResponse(BaseModel):
    """The spatial organization agreed so far (empty until the assistant proposes one)."""

    spaces: list[SpaceResponse]
    relationships: list[RelationshipResponse]
    latest_image_version: int | None = Field(
        description="Latest picture of the organization: GET /concept/{session_id}/images/{n}"
    )
    is_validated: bool = Field(
        description="True once the user accepted the organization together with a picture"
    )


class ChatResponse(BaseModel):
    """The assistant's reply, with the session to reuse on the next turn."""

    session_id: UUID
    step: int = Field(
        ge=1, description="Number of the workshop step the session is in after this turn"
    )
    reply: str
    information: InformationResponse
    concept: ConceptResponse
    spatial_design: SpatialDesignResponse
