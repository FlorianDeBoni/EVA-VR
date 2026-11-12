from dataclasses import replace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.services import chatService as chat_module
from backend.services.chatService import ChatService
from backend.services.errors import SessionNotFoundError
from backend.src.graph import graph as graph_module
from backend.src.graph.graph import MainGraph
from backend.src.graph.state import GraphState
from backend.src.graph.subgraphs.concept_design.graph import ConceptDesignGraph
from backend.src.graph.subgraphs.information_gathering.graph import InformationGatheringGraph
from backend.src.graph.tools.concept_design.schemas import ConceptDesign
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


NO_CONCEPT = ConceptDesign(reference_count=0, latest_version=None, is_validated=False)


class FakeConceptService:
    """Stands in for ConceptDesignService: nothing done yet."""

    def get_concept_design(self, session_id):
        return NO_CONCEPT

    def get_reference_images(self, session_id):
        return []

    def get_concept_image(self, session_id, version=None):
        return None


class FakeLLM:
    def __init__(self, *responses):
        self._responses = list(responses)

    def bind_tools(self, _tools, **kwargs):
        return self

    def invoke(self, messages):
        return self._responses.pop(0)


class FakePrompts:
    def get(self, name, **variables):
        return f"PROMPT {name}"


class FakeDatabase:
    """Stands in for DatabaseService: one known session, records updates."""

    def __init__(self, session_id=None):
        self.session_id = session_id
        self.updates = []

    def get_information(self, session_id):
        if session_id != self.session_id:
            raise SessionNotFoundError(f"session {session_id} not found")
        return EMPTY

    def update_information(self, session_id, information):
        self.updates.append((session_id, information))


def _subgraph(llm):
    return InformationGatheringGraph(llm=llm, prompt_service=FakePrompts()).graph


def _state(session_id=None, text="hi"):
    return {
        "messages": [HumanMessage(text)],
        "session_id": session_id or uuid4(),
        "information": EMPTY,
        "concept_design": NO_CONCEPT,
    }


# ---- main graph


def test_router_picks_gather_information_until_the_information_is_validated():
    assert MainGraph(subgraphs={}).route(_state()) == "gather_information"


def test_router_picks_concept_design_once_the_information_is_validated():
    state = {**_state(), "information": replace(EMPTY, is_validated=True)}

    assert MainGraph(subgraphs={}).route(state) == "concept_design"


def test_default_subgraphs_register_the_gather_information_graph(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        graph_module,
        "get_information_gathering_graph",
        lambda: type("G", (), {"graph": sentinel})(),
    )
    monkeypatch.setattr(
        graph_module,
        "get_concept_design_graph",
        lambda: type("G", (), {"graph": "concept"})(),
    )
    assert MainGraph().subgraphs == {"gather_information": sentinel, "concept_design": "concept"}


def test_main_graph_routes_the_state_through_the_subgraph(monkeypatch):
    db = FakeDatabase()
    monkeypatch.setattr(tools, "get_database_service", lambda: db)
    llm = FakeLLM(
        AIMessage(
            content="",
            tool_calls=[{"name": "update_information", "args": {"goal": "g"}, "id": "c1"}],
        ),
        AIMessage(content="Who will use the room?"),
    )
    main = MainGraph(subgraphs={"gather_information": _subgraph(llm)}).graph

    result = main.invoke(_state())

    assert result["messages"][-1].content == "Who will use the room?"
    assert result["information"].goal == "g"
    assert db.updates[0][1].goal == "g"


def _concept_subgraph(llm):
    return ConceptDesignGraph(
        llm=llm, prompt_service=FakePrompts(), concept_service=FakeConceptService()
    ).graph


def test_validating_the_information_continues_with_the_concept_design_in_the_same_turn(
    monkeypatch,
):
    db = FakeDatabase()
    monkeypatch.setattr(tools, "get_database_service", lambda: db)
    complete = replace(EMPTY, user_type="kids", number_of_users=4, task_description="t", goal="g")
    gather_llm = FakeLLM(
        AIMessage(content="", tool_calls=[{"name": "validate_information", "args": {}, "id": "c1"}])
    )
    concept_llm = FakeLLM(AIMessage(content="Thanks! Let's design the room."))
    main = MainGraph(
        subgraphs={
            "gather_information": _subgraph(gather_llm),
            "concept_design": _concept_subgraph(concept_llm),
        }
    ).graph

    result = main.invoke({**_state(), "information": complete})

    assert result["information"].is_validated is True
    assert result["messages"][-1].content == "Thanks! Let's design the room."


def test_validated_information_goes_straight_to_the_concept_design():
    gather_llm = FakeLLM()
    concept_llm = FakeLLM(AIMessage(content="Here are three references."))
    main = MainGraph(
        subgraphs={
            "gather_information": _subgraph(gather_llm),
            "concept_design": _concept_subgraph(concept_llm),
        }
    ).graph

    result = main.invoke({**_state(), "information": replace(EMPTY, is_validated=True)})

    assert result["messages"][-1].content == "Here are three references."


def test_main_graph_and_subgraphs_share_the_same_state_schema():
    main = MainGraph(subgraphs={"gather_information": _subgraph(FakeLLM())}).compile()
    sub = InformationGatheringGraph(llm=FakeLLM(), prompt_service=FakePrompts()).compile()

    assert main.builder.state_schema is GraphState
    assert sub.builder.state_schema is GraphState


def test_shared_main_graph_is_cached():
    graph_module.get_main_graph.cache_clear()
    assert graph_module.get_main_graph() is graph_module.get_main_graph()


# ---- chat service


class FakeGraph:
    def __init__(self):
        self.seen = None

    def invoke(self, state):
        self.seen = state
        return {**state, "messages": [*state["messages"], AIMessage(content="reply")]}


def test_run_passes_the_state_to_the_main_graph():
    graph = FakeGraph()
    state = _state()

    result = ChatService(
        graph=graph, database_service=FakeDatabase(), concept_service=FakeConceptService()
    ).run(state)

    assert graph.seen is state
    assert result["messages"][-1].content == "reply"


def test_chat_builds_the_state_from_the_session():
    session_id = uuid4()
    graph = FakeGraph()
    service = ChatService(
        graph=graph, database_service=FakeDatabase(session_id), concept_service=FakeConceptService()
    )
    messages = [HumanMessage("hello")]

    result = service.chat(session_id, messages)

    assert graph.seen == {
        "messages": messages,
        "session_id": session_id,
        "information": EMPTY,
        "concept_design": NO_CONCEPT,
    }
    assert result["messages"][-1].content == "reply"


def test_chat_unknown_session_raises_before_running_the_graph():
    graph = FakeGraph()
    service = ChatService(
        graph=graph, database_service=FakeDatabase(uuid4()), concept_service=FakeConceptService()
    )

    with pytest.raises(SessionNotFoundError):
        service.chat(uuid4(), [HumanMessage("hello")])
    assert graph.seen is None


def test_chat_end_to_end_with_the_real_main_graph(monkeypatch):
    session_id = uuid4()
    db = FakeDatabase(session_id)
    monkeypatch.setattr(tools, "get_database_service", lambda: db)
    llm = FakeLLM(
        AIMessage(
            content="",
            tool_calls=[{"name": "update_information", "args": {"user_type": "kids"}, "id": "c1"}],
        ),
        AIMessage(content="How many of you?"),
    )
    main = MainGraph(subgraphs={"gather_information": _subgraph(llm)}).graph

    state = ChatService(graph=main, database_service=db, concept_service=FakeConceptService()).chat(
        session_id, [HumanMessage("kids")]
    )

    assert state["messages"][-1].content == "How many of you?"
    assert state["information"].user_type == "kids"
    assert db.updates[0][0] == session_id


def test_shared_service_is_cached():
    chat_module.get_chat_service.cache_clear()
    assert chat_module.get_chat_service() is chat_module.get_chat_service()


def test_chat_service_builds_its_concept_service_lazily(monkeypatch):
    monkeypatch.setattr(chat_module, "get_concept_design_service", lambda: "concepts")

    assert ChatService(graph=FakeGraph()).concept_service == "concepts"
