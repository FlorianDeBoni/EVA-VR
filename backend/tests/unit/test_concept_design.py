from dataclasses import replace
from uuid import uuid4

import pytest
from fakes import FakeConceptService, FakeGenerator, b64, reference
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.api.main import app
from backend.api.routes import concept as route
from backend.src.graph.subgraphs.concept_design.graph import ConceptDesignGraph
from backend.src.graph.tools.concept_design import tool as tools
from backend.src.graph.tools.concept_design.schemas import ConceptDesign, ConceptImage
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.generate_image import tool as generate_tool

INFO = InformationToGather("architects", 5, "brainstorm", "find ideas", [], True)
NOTHING = ConceptDesign(reference_count=0, latest_version=None, is_validated=False)


@pytest.fixture
def service(monkeypatch):
    fake = FakeConceptService()
    monkeypatch.setattr(tools, "get_concept_design_service", lambda: fake)
    monkeypatch.setattr(route, "get_concept_design_service", lambda: fake)
    return fake


@pytest.fixture
def generator(monkeypatch, service):
    fake = FakeGenerator()
    monkeypatch.setattr(generate_tool, "get_image_generator_service", lambda: fake)
    monkeypatch.setattr(generate_tool, "get_concept_design_service", lambda: service)
    return fake


def state(concept=NOTHING):
    return {"session_id": uuid4(), "information": INFO, "concept_design": concept}


# ---- validate_concept


def test_validate_concept_flags_the_latest_version_by_default(service):
    service.versions = [ConceptImage(1, b64(b"v1"), "image/png", "p")]

    command = tools.validate_concept.func(
        state=state(ConceptDesign(0, 1, False)), tool_call_id="c1"
    )

    assert service.validated == 1
    assert command.update["concept_design"].is_validated is True


def test_validate_concept_refuses_without_image_or_with_a_wrong_version(service):
    nothing = tools.validate_concept.func(state=state(), tool_call_id="c1")
    wrong = tools.validate_concept.func(
        state=state(ConceptDesign(0, 1, False)), tool_call_id="c1", version=5
    )

    assert "no concept image" in nothing.update["messages"][0].content
    assert "version 5" in wrong.update["messages"][0].content
    assert service.validated is None
    assert "concept_design" not in nothing.update and "concept_design" not in wrong.update


# ---- subgraph


class FakeLLM:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def bind_tools(self, bound, **kwargs):
        self.bound_tools = [t.name for t in bound]
        self.bind_kwargs = kwargs
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self._responses.pop(0)


class FakePrompts:
    def get(self, name, **variables):
        return f"PROMPT {name}\n{variables['status']}"


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1"}])


def run(llm, service, concept=NOTHING, text="hello"):
    graph = ConceptDesignGraph(llm=llm, prompt_service=FakePrompts(), concept_service=service)
    return graph.graph.invoke(
        {
            "messages": [HumanMessage(text)],
            "session_id": uuid4(),
            "information": INFO,
            "concept_design": concept,
        }
    )


def test_agent_gets_the_three_tools_one_call_at_a_time(service):
    llm = FakeLLM(AIMessage(content="hi"))

    run(llm, service)

    assert llm.bound_tools == [
        "search_web_images",
        "generate_image",
        "validate_concept",
    ]
    assert llm.bind_kwargs == {"parallel_tool_calls": False}


def test_agent_without_images_sends_only_text(service):
    llm = FakeLLM(AIMessage(content="Let me search."))

    run(llm, service)

    system, *rest = llm.calls[0]
    assert isinstance(system, SystemMessage) and "none yet: search for them now" in system.content
    assert [type(m) for m in rest] == [HumanMessage]


def test_agent_sees_the_reference_images_and_the_latest_concept(service):
    service.references = [reference(1), reference(2)]
    service.versions = [
        ConceptImage(1, b64(b"v1"), "image/png", "p"),
        ConceptImage(2, b64(b"v2"), "image/png", "p"),
    ]
    llm = FakeLLM(AIMessage(content="Which elements do you like?"))

    run(llm, service, ConceptDesign(2, 2, False), "the wooden ceiling")

    system, context, user = llm.calls[0]
    assert "2 reference images" in system.content and "latest is version 2" in system.content
    urls = [p["image_url"]["url"] for p in context.content if p["type"] == "image_url"]
    assert urls == [
        f"data:image/jpeg;base64,{reference(1).image_b64}",
        f"data:image/jpeg;base64,{reference(2).image_b64}",
        f"data:image/png;base64,{b64(b'v2')}",
    ]
    texts = [p["text"] for p in context.content if p["type"] == "text"]
    assert any("Reference 1 (R1)" in t for t in texts)
    assert any("version 2" in t for t in texts)
    assert user.content == "the wooden ceiling"


def test_agent_sees_a_new_image_right_after_generating_it(service, generator):
    llm = FakeLLM(
        tool_call("generate_image", prompt="a studio"),
        AIMessage(content="Here it is. What would you change?"),
    )

    result = run(llm, service)

    assert result["concept_design"].latest_version == 1
    assert result["messages"][-1].content == "Here it is. What would you change?"
    first, second = llm.calls
    assert all(not isinstance(m.content, list) for m in first[1:])
    context = second[1]
    assert any(p["type"] == "image_url" for p in context.content)
    assert isinstance(second[-1], ToolMessage)


def test_agent_stops_right_after_the_validation(service):
    # The next step speaks next: the agent must not be called again after the validation.
    service.versions = [ConceptImage(1, b64(b"v1"), "image/png", "p")]
    llm = FakeLLM(tool_call("validate_concept"))

    result = run(llm, service, ConceptDesign(0, 1, False), "yes, keep it")

    assert service.validated == 1
    assert result["concept_design"].is_validated is True
    assert isinstance(result["messages"][-1], ToolMessage)
    assert len(llm.calls) == 1


def test_agent_keeps_talking_when_the_validation_is_refused(service):
    llm = FakeLLM(tool_call("validate_concept"), AIMessage(content="Let's make a first image."))

    result = run(llm, service, NOTHING, "yes")

    assert result["concept_design"].is_validated is False
    assert result["messages"][-1].content == "Let's make a first image."


@pytest.mark.parametrize(
    ("concept", "expected"),
    [
        (NOTHING, "- Concept validated by the user: no"),
        (replace(NOTHING, is_validated=True), "- Concept validated by the user: yes"),
    ],
)
def test_status_tells_whether_the_concept_is_validated(concept, expected):
    assert expected in ConceptDesignGraph.status(concept)


def test_shared_graph_is_cached():
    from backend.src.graph.subgraphs.concept_design import graph as module

    module.get_concept_design_graph.cache_clear()
    assert module.get_concept_design_graph() is module.get_concept_design_graph()


# ---- image routes


def test_routes_serve_the_stored_images(service):
    session_id = uuid4()
    service.references = [reference(1)]
    service.versions = [ConceptImage(1, b64(b"png"), "image/png", "p")]
    service.validated = 1
    client = TestClient(app)

    ref = client.get(f"/concept/{session_id}/references/1")
    version = client.get(f"/concept/{session_id}/images/1")
    final = client.get(f"/concept/{session_id}/validated")

    assert (ref.status_code, ref.headers["content-type"], ref.content) == (
        200,
        "image/jpeg",
        b"ref\x01",
    )
    assert version.content == b"png" and "immutable" in version.headers["cache-control"]
    assert final.content == b"png" and final.headers["content-type"] == "image/png"


def test_routes_answer_404_for_missing_images(service):
    client = TestClient(app)
    session_id = uuid4()

    for path in ("references/1", "images/1", "validated"):
        assert client.get(f"/concept/{session_id}/{path}").status_code == 404


def test_the_graph_builds_its_services_lazily(monkeypatch):
    from backend.src.graph.subgraphs.concept_design import graph as module

    monkeypatch.setattr(module, "get_prompt_service", lambda: "prompts")
    monkeypatch.setattr(module, "get_concept_design_service", lambda: "concepts")
    graph = ConceptDesignGraph(llm=FakeLLM())

    assert (graph.prompt_service, graph.concept_service) == ("prompts", "concepts")
