from dataclasses import asdict, replace

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from backend.services.errors import SpatialDesignNotFoundError, SpatialImageOutdatedError
from backend.services.spatialDesignService import get_spatial_design_service
from backend.src.graph.tools.spatial_design.schemas import (
    Relationship,
    RelationshipInput,
    Space,
    SpaceInput,
    SpatialDesign,
    UpdateSpatialDesignInput,
    ValidateSpatialDesignInput,
)

MIN_SPACES = 2


def _result(tool_call_id: str, text: str, design: SpatialDesign | None = None) -> Command:
    """Answer the model, and refresh the graph state's spatial design when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if design is not None:
        update["spatial_design"] = design
    return Command(update=update)


def _spaces(items: list) -> list[Space]:
    spaces = []
    for item in items:
        data = SpaceInput.model_validate(item).model_dump()
        data["name"] = data["name"].strip()
        spaces.append(Space(**data))
    return spaces


def _relationships(items: list, spaces: list[Space]) -> tuple[list[Relationship], list[str]]:
    """The relationships with the spelling of the space names, and what is wrong with them."""
    names = {space.name.casefold(): space.name for space in spaces}
    relationships: list[Relationship] = []
    problems: list[str] = []
    for item in items:
        # Either what the model sent, or the relationships already saved (kept as they are).
        data = (
            asdict(item)
            if isinstance(item, Relationship)
            else (RelationshipInput.model_validate(item).model_dump())
        )
        ends = [data["from_space"].strip(), data["to_space"].strip()]
        unknown = [end for end in ends if end.casefold() not in names]
        if unknown:
            problems.append(f"'{ends[0]}' - '{ends[1]}': unknown space '{unknown[0]}'")
        elif ends[0].casefold() == ends[1].casefold():
            problems.append(f"'{ends[0]}' is linked to itself")
        else:
            data["from_space"], data["to_space"] = (names[end.casefold()] for end in ends)
            relationships.append(Relationship(**data))
    return relationships, problems


@tool("update_spatial_design", args_schema=UpdateSpatialDesignInput)
def update_spatial_design(
    state: dict,
    tool_call_id: str,
    spaces: list[SpaceInput] | None = None,
    relationships: list[RelationshipInput] | None = None,
) -> Command:
    """Record the spaces of the room and how they relate, as agreed with the user.

    Send the complete list of spaces and/or the complete list of relationships (each list
    replaces the previous one); leave out a list that did not change. Relationships name
    the spaces they link, and every name must be in the list of spaces. It is saved right
    away. Changing anything resets the validation, so the user must confirm again.
    """
    if spaces is None and relationships is None:
        return _result(tool_call_id, "Nothing to update: no list was provided.")

    current: SpatialDesign = state["spatial_design"]
    new_spaces = _spaces(spaces) if spaces is not None else current.spaces
    names = [space.name.casefold() for space in new_spaces]
    if len(set(names)) != len(names):
        return _result(tool_call_id, "Nothing saved: two spaces have the same name.")

    raw = relationships if relationships is not None else current.relationships
    new_relationships, problems = _relationships(raw, new_spaces)
    if problems:
        hint = "" if relationships is not None else " Send the updated list of relationships too."
        return _result(tool_call_id, f"Nothing saved. {'; '.join(problems)}.{hint}")

    updated = replace(
        current, spaces=new_spaces, relationships=new_relationships, is_validated=False
    )
    get_spatial_design_service().save_draft(state["session_id"], updated)
    return _result(
        tool_call_id,
        f"Saved: {len(new_spaces)} spaces, {len(new_relationships)} relationships.",
        updated,
    )


@tool("validate_spatial_design", args_schema=ValidateSpatialDesignInput)
def validate_spatial_design(state: dict, tool_call_id: str, version: int | None = None) -> Command:
    """Keep the spatial design and its picture as final, as accepted by the user.

    Call it as soon as the user has accepted the picture: they clearly said they are happy with
    it or want to move on, or they answered yes to your one closing question. Never call it
    while they still ask for changes, and do not ask them to confirm again if they already did.
    It refuses if the design has fewer than two spaces or no relationship, if no picture was
    generated, or if the design changed after the picture (generate a new one).
    """
    design: SpatialDesign = state["spatial_design"]
    if len(design.spaces) < MIN_SPACES:
        return _result(
            tool_call_id, f"Cannot validate yet: at least {MIN_SPACES} spaces are needed."
        )
    if not design.relationships:
        return _result(tool_call_id, "Cannot validate yet: no relationship between spaces.")

    version = version or design.latest_image_version
    if version is None:
        return _result(
            tool_call_id,
            "Cannot validate yet: no picture of the spatial organization was generated. "
            "Generate one first.",
        )

    try:
        get_spatial_design_service().validate(state["session_id"], version)
    except SpatialDesignNotFoundError:
        return _result(tool_call_id, f"Cannot validate: there is no picture version {version}.")
    except SpatialImageOutdatedError:
        return _result(
            tool_call_id,
            "Cannot validate: the organization changed after that picture. "
            "Generate a new picture of the current organization first.",
        )
    return _result(
        tool_call_id,
        f"Spatial design validated with picture version {version}.",
        replace(design, is_validated=True),
    )
