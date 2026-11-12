from dataclasses import replace

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from backend.services.conceptDesignService import get_concept_design_service
from backend.services.errors import ConceptImageNotFoundError
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ValidateConceptInput,
)


def _result(tool_call_id: str, text: str, concept: ConceptDesign | None = None) -> Command:
    """Answer the model, and refresh the graph state's concept design when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if concept is not None:
        update["concept_design"] = concept
    return Command(update=update)


@tool("validate_concept", args_schema=ValidateConceptInput)
def validate_concept(state: dict, tool_call_id: str, version: int | None = None) -> Command:
    """Keep a concept image as the final concept of the room, as accepted by the user.

    Call it as soon as the user has accepted that image: they clearly said they are happy with
    it or want to move on, or they answered yes to your one closing question. Never call it
    while they still ask for changes, and do not ask them to confirm again if they already did.
    It refuses if no image was generated yet.
    """
    concept: ConceptDesign = state["concept_design"]
    version = version or concept.latest_version
    if version is None:
        return _result(tool_call_id, "Cannot validate yet: no concept image was generated.")

    try:
        get_concept_design_service().validate_concept(state["session_id"], version)
    except ConceptImageNotFoundError:
        return _result(tool_call_id, f"There is no concept version {version}.")
    return _result(
        tool_call_id, f"Concept version {version} validated.", replace(concept, is_validated=True)
    )
