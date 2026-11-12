from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


class ImageCategory(StrEnum):
    """Kinds of images we are looking for."""

    BUILDING = "building"
    INTERIOR = "interior"
    INSTALLATION = "installation"


@dataclass(frozen=True)
class ImageHit:
    """One ranked image result."""

    title: str
    image_url: str
    thumbnail_url: str
    page_url: str
    width: int
    height: int
    category: ImageCategory
    score: float


class ImageScore(BaseModel):
    """Structured-output item: the vision model's score for one image."""

    index: int
    score: float = Field(ge=0, le=1, description="1 = perfect match for the request")
    reason: str = Field(description="One short sentence")


class Scores(BaseModel):
    """Structured-output schema for one scoring batch."""

    scores: list[ImageScore]


@dataclass(frozen=True)
class RankedImage:
    """An image hit with the AI relevance score and the reason behind it."""

    hit: ImageHit
    score: float
    reason: str


class SearchWebImagesInput(BaseModel):
    """Arguments the agent provides when calling the tool."""

    query: str = Field(min_length=1, description="Keywords, e.g. 'brutalist concrete library'")
    criteria: str = Field(
        default="", description="What a good image looks like, e.g. 'interior view, no people'"
    )
    # Injected by the graph, hidden from the model.
    state: Annotated[dict, InjectedState]
    tool_call_id: Annotated[str, InjectedToolCallId]


@dataclass(frozen=True)
class DownloadedImage:
    """A ranked image whose file was downloaded and normalized (JPEG bytes)."""

    ranked: RankedImage
    data: bytes
    mime_type: str
