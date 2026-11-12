from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from backend.src.graph.tools.concept_design.schemas import ConceptDesign
from backend.src.graph.tools.gather_information.schemas import InformationToGather


class GraphState(TypedDict):
    """State shared by the main graph and every subgraph (same schema, no mapping)."""

    messages: Annotated[list[AnyMessage], add_messages]
    # Session whose row the tools update.
    session_id: UUID
    # What is known so far; kept in sync with the database by the tools.
    information: InformationToGather
    # Progress of the concept design step; kept in sync with the database by its tools.
    concept_design: ConceptDesign
