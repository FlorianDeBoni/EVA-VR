from dataclasses import replace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.src.graph.subgraphs.information_gathering.graph import InformationGatheringGraph
from backend.src.graph.tools.gather_information import tool as tools
from backend.src.graph.tools.gather_information.schemas import InformationToGather

EMPTY = InformationToGather(
    user_type="",
    number_of_users=None,
    task_description="",
    goal="",
    must_have_features=[],
    is_validated=False,
)
COMPLETE = InformationToGather(
    user_type="architects",
    number_of_users=5,
    task_description="brainstorming",
    goal="find a concept",
    must_have_features=["whiteboard"],
    is_validated=False,
)


class FakeDatabase:
    def __init__(self):
        self.updates = []

    def update_information(self, session_id, information):
        self.updates.append((session_id, information))


@pytest.fixture
def database(monkeypatch):
    db = FakeDatabase()
    monkeypatch.setattr(tools, "get_database_service", lambda: db)
    return db


class FakeLLM:
    """Answers with the scripted messages in order and records what it was asked."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []
        self.bound_tools = None

    def bind_tools(self, bound, **kwargs):
        self.bound_tools = [t.name for t in bound]
        self.bind_kwargs = kwargs
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self._responses.pop(0)


class FakePrompts:
    def get(self, name, **variables):
        return f"PROMPT {name}: {variables['information']}"


def _call(name, call_id="c1", **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _run(llm, information, text="hello"):
    agent = InformationGatheringGraph(llm=llm, prompt_service=FakePrompts())
    session_id = uuid4()
    state = {
        "messages": [HumanMessage(text)],
        "session_id": session_id,
        "information": information,
    }
    return agent.graph.invoke(state), session_id


# ---- tools


def test_update_information_saves_only_given_fields_and_resets_validation(database):
    state = {"session_id": uuid4(), "information": replace(COMPLETE, is_validated=True)}

    command = tools.update_information.func(state=state, tool_call_id="c1", goal="new goal")

    new = command.update["information"]
    assert (new.goal, new.user_type, new.number_of_users) == ("new goal", "architects", 5)
    assert new.is_validated is False
    assert database.updates == [(state["session_id"], new)]
    assert "goal" in command.update["messages"][0].content


def test_update_information_without_fields_does_nothing(database):
    state = {"session_id": uuid4(), "information": EMPTY}

    command = tools.update_information.func(state=state, tool_call_id="c1")

    assert database.updates == []
    assert "information" not in command.update


def test_validate_refuses_when_required_fields_are_missing(database):
    state = {"session_id": uuid4(), "information": replace(COMPLETE, goal="")}

    command = tools.validate_information.func(state=state, tool_call_id="c1")

    assert database.updates == []
    assert "goal" in command.update["messages"][0].content
    assert "information" not in command.update


def test_validate_sets_the_flag_when_complete(database):
    state = {"session_id": uuid4(), "information": replace(COMPLETE, must_have_features=[])}

    command = tools.validate_information.func(state=state, tool_call_id="c1")

    assert command.update["information"].is_validated is True
    assert database.updates[0][1].is_validated is True


# ---- agent graph


def test_agent_records_information_then_asks_the_next_question(database):
    llm = FakeLLM(
        _call("update_information", user_type="architects", number_of_users=5),
        AIMessage(content="What will you create in the room?"),
    )

    result, session_id = _run(llm, EMPTY, "We are 5 architects")

    assert llm.bound_tools == ["update_information", "validate_information"]
    # Parallel tool calls would lose updates (stale full-row writes), so they are disabled.
    assert llm.bind_kwargs == {"parallel_tool_calls": False}
    assert result["messages"][-1].content == "What will you create in the room?"
    assert any(isinstance(m, ToolMessage) for m in result["messages"])
    assert result["information"].user_type == "architects"
    assert result["information"].number_of_users == 5
    assert database.updates[0][0] == session_id
    # The second model call saw the system prompt rendered with the new information.
    system = llm.calls[1][0]
    assert isinstance(system, SystemMessage)
    assert "architects" in system.content


def test_agent_validates_after_confirmation(database):
    llm = FakeLLM(
        _call("validate_information"),
        AIMessage(content="Thanks, let's start designing!"),
    )

    result, _ = _run(llm, COMPLETE, "Yes, that's right")

    assert result["information"].is_validated is True
    assert database.updates[-1][1].is_validated is True
    assert result["messages"][-1].content == "Thanks, let's start designing!"


def test_agent_ends_the_turn_without_tool_calls(database):
    llm = FakeLLM(AIMessage(content="Who will use the room?"))

    result, _ = _run(llm, EMPTY)

    assert result["messages"][-1].content == "Who will use the room?"
    assert database.updates == []
    assert len(llm.calls) == 1


def test_agent_opens_the_conversation_when_there_is_no_message_yet(database):
    llm = FakeLLM(AIMessage(content="Welcome! Who will use the room?"))
    agent = InformationGatheringGraph(llm=llm, prompt_service=FakePrompts())

    result = agent.graph.invoke({"messages": [], "session_id": uuid4(), "information": EMPTY})

    assert result["messages"][-1].content == "Welcome! Who will use the room?"
    assert len(llm.calls) == 1
    assert len(llm.calls[0]) == 1 and isinstance(llm.calls[0][0], SystemMessage)
    assert database.updates == []
