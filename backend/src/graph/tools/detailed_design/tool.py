from dataclasses import asdict, replace

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from backend.services.detailedDesignService import get_detailed_design_service
from backend.services.errors import DetailedDesignNotFoundError, DetailedImageOutdatedError
from backend.src.graph.tools.detailed_design.rules import validation_problem
from backend.src.graph.tools.detailed_design.schemas import (
    Detail,
    DetailedDesign,
    DetailInput,
    UpdateDetailedDesignInput,
    ValidateDetailedDesignInput,
)


def _result(tool_call_id: str, text: str, design: DetailedDesign | None = None) -> Command:
    """Answer the model, and refresh the graph state's detailed design when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if design is not None:
        update["detailed_design"] = design
    return Command(update=update)


@tool("update_detailed_design", args_schema=UpdateDetailedDesignInput)
def update_detailed_design(state: dict, tool_call_id: str, details: list[DetailInput]) -> Command:
    """Record the details of the room (furniture, shapes, materials, colors…) agreed with the user.

    Send the complete list of details: it replaces the previous one. A detail belongs to a
    space of the validated spatial design (use its exact name) or, when it applies to the
    whole room, to none. It is saved right away. Changing anything resets the validation, so
    the user must accept the picture again.
    """
    spaces = {space.name.casefold(): space.name for space in state["spatial_design"].spaces}
    new_details: list[Detail] = []
    seen: set[tuple[str, str]] = set()
    problems: list[str] = []
    for item in details:
        data = (
            asdict(item)
            if isinstance(item, Detail)
            else DetailInput.model_validate(item).model_dump()
        )
        data["name"] = data["name"].strip()
        space = (data["space"] or "").strip()
        if space and space.casefold() not in spaces:
            problems.append(f"'{data['name']}': unknown space '{space}'")
            continue
        data["space"] = spaces[space.casefold()] if space else None
        key = (data["name"].casefold(), (data["space"] or "").casefold())
        if key in seen:
            problems.append(f"'{data['name']}' is listed twice")
            continue
        seen.add(key)
        new_details.append(Detail(**data))

    if problems:
        known = ", ".join(spaces.values()) or "none"
        return _result(tool_call_id, f"Nothing saved. {'; '.join(problems)}. Spaces: {known}.")

    current: DetailedDesign = state["detailed_design"]
    updated = replace(current, details=new_details, is_validated=False)
    get_detailed_design_service().save_draft(state["session_id"], updated)
    return _result(tool_call_id, f"Saved: {len(new_details)} details.", updated)


@tool("validate_detailed_design", args_schema=ValidateDetailedDesignInput)
def validate_detailed_design(state: dict, tool_call_id: str, version: int | None = None) -> Command:
    """Keep the detailed design and its picture as the final design, as accepted by the user.

    Call it as soon as the user has accepted the picture: they clearly said they are happy with
    it or want to finish, or they answered yes to your one closing question. Never call it
    while they still ask for changes, and do not ask them to confirm again if they already did.
    It refuses if there is no piece of furniture, if no picture was generated, or if the details
    changed after the picture (generate a new one).
    """
    design: DetailedDesign = state["detailed_design"]
    problem = validation_problem(design)
    if problem:
        return _result(tool_call_id, f"Cannot validate yet: {problem}")

    version = version or design.latest_image_version

    try:
        get_detailed_design_service().validate(state["session_id"], version)
    except DetailedDesignNotFoundError:
        return _result(tool_call_id, f"Cannot validate: there is no picture version {version}.")
    except DetailedImageOutdatedError:
        return _result(
            tool_call_id,
            "Cannot validate: the details changed after that picture. "
            "Generate a new picture of the current details first.",
        )
    return _result(
        tool_call_id,
        f"Detailed design validated with picture version {version}.",
        replace(design, is_validated=True),
    )
