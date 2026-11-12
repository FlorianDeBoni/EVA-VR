from dataclasses import replace

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from backend.services.databaseService import get_database_service
from backend.src.graph.tools.gather_information.schemas import (
    InformationToGather,
    UpdateInformationInput,
    ValidateInformationInput,
)


def _result(
    tool_call_id: str, text: str, information: InformationToGather | None = None
) -> Command:
    """Answer the model, and refresh the graph state's information when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if information is not None:
        update["information"] = information
    return Command(update=update)


@tool("update_information", args_schema=UpdateInformationInput)
def update_information(
    state: dict,
    tool_call_id: str,
    user_type: str | None = None,
    number_of_users: int | None = None,
    task_description: str | None = None,
    goal: str | None = None,
    must_have_features: list[str] | None = None,
) -> Command:
    """Record what the user just told you about their project.

    Send only the fields that are new or corrected. The information is saved right away.
    Changing anything resets the validation, so the user must confirm again.
    """
    changes = {
        key: value
        for key, value in {
            "user_type": user_type,
            "number_of_users": number_of_users,
            "task_description": task_description,
            "goal": goal,
            "must_have_features": must_have_features,
        }.items()
        if value is not None
    }
    if not changes:
        return _result(tool_call_id, "Nothing to update: no field was provided.")

    updated = replace(state["information"], **changes, is_validated=False)
    get_database_service().update_information(state["session_id"], updated)
    return _result(tool_call_id, f"Saved: {', '.join(changes)}.", updated)


@tool("validate_information", args_schema=ValidateInformationInput)
def validate_information(state: dict, tool_call_id: str) -> Command:
    """Mark the gathered information as validated by the user.

    Call it only after the user explicitly confirmed your summary. It refuses if a
    required field is still missing.
    """
    info: InformationToGather = state["information"]
    missing = [
        name
        for name, value in {
            "user_type": info.user_type,
            "number_of_users": info.number_of_users,
            "task_description": info.task_description,
            "goal": info.goal,
        }.items()
        if value is None or value == ""
    ]
    if missing:
        return _result(tool_call_id, f"Cannot validate yet, still missing: {', '.join(missing)}.")

    validated = replace(info, is_validated=True)
    get_database_service().update_information(state["session_id"], validated)
    return _result(tool_call_id, "Information validated.", validated)
