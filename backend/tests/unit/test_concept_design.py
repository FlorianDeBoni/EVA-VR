import base64
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from openai import BadRequestError

from backend.api.main import app
from backend.api.routes import concept as route
from backend.services.errors import ConceptImageNotFoundError
from backend.src.graph.subgraphs.concept_design.graph import ConceptDesignGraph
from backend.src.graph.tools.concept_design import tool as tools
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ConceptImage,
    ReferenceImage,
)
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.generate_image.schemas import GeneratedImage, ImageGenerationError

INFO = InformationToGather("architects", 5, "brainstorm", "find ideas", [], True)
NOTHING = ConceptDesign(reference_count=0, latest_version=None, is_validated=False)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class FakeConceptService:
    """In-memory ConceptDesignService."""

    def __init__(self, references=(), versions=()):
        self.references = list(references)
        self.versions = list(versions)
        self.validated = None

    def get_concept_design(self, session_id):
        return ConceptDesign(
            len(self.references), len(self.versions) or None, self.validated is not None
        )

    def replace_reference_images(self, session_id, images):
        self.references = list(images)

    def get_reference_images(self, session_id):
        return list(self.references)

    def get_reference_image(self, session_id, position):
        return next((r for r in self.references if r.position == position), None)

    def add_concept_image(self, session_id, image_b64, prompt):
        self.versions.append(ConceptImage(len(self.versions) + 1, image_b64, "image/png", prompt))
        self.validated = None
        return len(self.versions)

    def get_concept_image(self, session_id, version=None):
        if version is None:
            return self.versions[-1] if self.versions else None
        return next((v for v in self.versions if v.version == version), None)

    def validate_concept(self, session_id, version):
        if self.get_concept_image(session_id, version) is None:
            raise ConceptImageNotFoundError("missing")
        self.validated = version

    def get_validated_image(self, session_id):
        return (
            self.get_concept_image(session_id, self.validated).image_b64 if self.validated else None
        )


def reference(position, data=b"ref"):
    return ReferenceImage(
        position, b64(data + bytes([position])), "image/jpeg", f"R{position}", "", ""
    )


@pytest.fixture
def service(monkeypatch):
    fake = FakeConceptService()
    monkeypatch.setattr(tools, "get_concept_design_service", lambda: fake)
    monkeypatch.setattr(route, "get_concept_design_service", lambda: fake)
    return fake


class FakeGenerator:
    max_past_images = 3

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def generate(self, prompt, past_images=()):
        if self.error:
            raise self.error
        self.calls.append((prompt, list(past_images)))
        return GeneratedImage(b"generated", "image/png")


@pytest.fixture
def generator(monkeypatch):
    fake = FakeGenerator()
    monkeypatch.setattr(tools, "get_image_generator_service", lambda: fake)
    return fake


def state(concept=NOTHING):
    return {"session_id": uuid4(), "information": INFO, "concept_design": concept}


# ---- generate_concept_image


def test_first_generation_draws_from_the_chosen_references(service, generator):
    service.references = [reference(1), reference(2), reference(3)]

    command = tools.generate_concept_image.func(
        state=state(ConceptDesign(3, None, False)),
        tool_call_id="c1",
        prompt="A warm timber studio",
        reference_numbers=[3, 1, 3],
    )

    prompt, past = generator.calls[0]
    assert [i.data for i in past] == [b"ref\x03", b"ref\x01"]
    assert "Image 1: reference 3" in prompt and "Image 2: reference 1" in prompt
    assert prompt.endswith("A warm timber studio")
    assert service.versions[0].prompt == "A warm timber studio"
    assert base64.b64decode(service.versions[0].image_b64) == b"generated"
    assert command.update["concept_design"].latest_version == 1


def test_next_generations_iterate_on_the_latest_version_first(service, generator):
    service.references = [reference(1), reference(2), reference(3)]
    service.versions = [
        ConceptImage(1, b64(b"v1"), "image/png", "p"),
        ConceptImage(2, b64(b"v2"), "image/png", "p"),
    ]

    command = tools.generate_concept_image.func(
        state=state(ConceptDesign(3, 2, True)),
        tool_call_id="c1",
        prompt="Make it brighter",
        reference_numbers=[1, 2, 3],
    )

    prompt, past = generator.calls[0]
    # Limit of 3 past images: the latest concept first, then the references, in order.
    assert [i.data for i in past] == [b"v2", b"ref\x01", b"ref\x02"]
    assert "Image 1: the current concept (version 2)" in prompt
    assert command.update["concept_design"] == ConceptDesign(3, 3, False)


def test_generation_can_go_back_to_an_earlier_version(service, generator):
    service.versions = [
        ConceptImage(1, b64(b"v1"), "image/png", "p"),
        ConceptImage(2, b64(b"v2"), "image/png", "p"),
    ]

    tools.generate_concept_image.func(
        state=state(ConceptDesign(0, 2, False)), tool_call_id="c1", prompt="p", base_version=1
    )

    assert [i.data for i in generator.calls[0][1]] == [b"v1"]


def test_generation_without_any_past_image_sends_the_bare_prompt(service, generator):
    tools.generate_concept_image.func(state=state(), tool_call_id="c1", prompt="a room")

    assert generator.calls == [("a room", [])]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"reference_numbers": [2]}, "reference image 2"), ({"base_version": 7}, "version 7")],
)
def test_generation_refuses_unknown_images(service, generator, kwargs, message):
    command = tools.generate_concept_image.func(
        state=state(), tool_call_id="c1", prompt="p", **kwargs
    )

    assert message in command.update["messages"][0].content
    assert generator.calls == [] and service.versions == []


def test_a_refused_or_empty_generation_is_reported_to_the_model(service, monkeypatch):
    request = httpx.Request("POST", "http://x")
    refused = BadRequestError("no", response=httpx.Response(400, request=request), body=None)
    for error in (ImageGenerationError("empty"), refused):
        monkeypatch.setattr(tools, "get_image_generator_service", lambda e=error: FakeGenerator(e))

        command = tools.generate_concept_image.func(state=state(), tool_call_id="c1", prompt="p")

        assert "could not be generated" in command.update["messages"][0].content
        assert "concept_design" not in command.update
    assert service.versions == []


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
        "generate_concept_image",
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
        tool_call("generate_concept_image", prompt="a studio"),
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


def test_agent_validates_the_concept_after_the_confirmation(service):
    service.versions = [ConceptImage(1, b64(b"v1"), "image/png", "p")]
    llm = FakeLLM(tool_call("validate_concept"), AIMessage(content="Great, concept saved."))

    result = run(llm, service, ConceptDesign(0, 1, False), "yes, keep it")

    assert service.validated == 1
    assert result["concept_design"].is_validated is True
    assert result["messages"][-1].content == "Great, concept saved."


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
