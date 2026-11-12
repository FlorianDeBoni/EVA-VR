import base64
from dataclasses import replace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.services.errors import SpatialDesignNotFoundError, SpatialImageOutdatedError
from backend.src.graph.subgraphs.spatial_design import graph as graph_module
from backend.src.graph.subgraphs.spatial_design.graph import SpatialDesignGraph
from backend.src.graph.tools.concept_design.schemas import ConceptDesign, ConceptImage
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.spatial_design import tool as tools
from backend.src.graph.tools.spatial_design.schemas import (
    Relationship,
    RelationshipInput,
    RelationType,
    Space,
    SpaceInput,
    SpatialDesign,
)

INFO = InformationToGather("architects", 5, "brainstorm", "find ideas", [], True)
EMPTY = SpatialDesign([], [], False)
LAB = Space("Lab", "build", ["prototyping"], 4, "large")
LOUNGE = Space("Lounge", "rest")
LINK = Relationship("Lab", "Lounge", RelationType.VISUAL_LINK, "see each other")
DRAFT = SpatialDesign([LAB, LOUNGE], [LINK], False)
PICTURED = replace(DRAFT, latest_image_version=4)


class FakeSpatialService:
    """In-memory SpatialDesignService."""

    def __init__(self, error=None):
        self.saved = []
        self.validated = []
        self.error = error

    def save_draft(self, session_id, design):
        self.saved.append((session_id, design))

    def validate(self, session_id, version):
        if self.error:
            raise self.error
        self.validated.append((session_id, version))


@pytest.fixture
def service(monkeypatch):
    fake = FakeSpatialService()
    monkeypatch.setattr(tools, "get_spatial_design_service", lambda: fake)
    return fake


def state(design=EMPTY):
    return {"session_id": uuid4(), "information": INFO, "spatial_design": design}


def space(name, **kwargs):
    return SpaceInput(name=name, purpose=f"{name} purpose", **kwargs)


def link(a, b, kind=RelationType.ADJACENT):
    return RelationshipInput(from_space=a, to_space=b, type=kind, description="d")


def message(command):
    return command.update["messages"][0].content


# ---- update_spatial_design


def test_the_model_only_sees_the_two_lists():
    props = tools.update_spatial_design.tool_call_schema.model_json_schema()["properties"]

    assert set(props) == {"spaces", "relationships"}


def test_update_saves_the_draft_and_reopens_the_validation(service):
    current = replace(DRAFT, is_validated=True)
    command = tools.update_spatial_design.func(
        state=state(current),
        tool_call_id="c1",
        spaces=[space("Lab"), space("Lounge"), space("Library")],
        relationships=[link("Lab", "Library")],
    )

    updated = command.update["spatial_design"]
    assert [s.name for s in updated.spaces] == ["Lab", "Lounge", "Library"]
    assert updated.relationships == [Relationship("Lab", "Library", RelationType.ADJACENT, "d")]
    assert updated.is_validated is False
    assert service.saved[0][1] == updated
    assert "3 spaces, 1 relationships" in message(command)


def test_update_keeps_the_version_of_the_latest_picture(service):
    command = tools.update_spatial_design.func(
        state=state(PICTURED), tool_call_id="c1", relationships=[link("Lounge", "Lab")]
    )

    assert command.update["spatial_design"].latest_image_version == 4


def test_update_keeps_the_list_that_was_not_sent(service):
    only_spaces = tools.update_spatial_design.func(
        state=state(DRAFT), tool_call_id="c1", spaces=[space("Lab"), space("Lounge")]
    )
    only_relationships = tools.update_spatial_design.func(
        state=state(DRAFT), tool_call_id="c1", relationships=[link("Lounge", "Lab")]
    )

    assert only_spaces.update["spatial_design"].relationships == [LINK]
    assert only_relationships.update["spatial_design"].spaces == [LAB, LOUNGE]


def test_update_accepts_plain_dicts_and_fixes_the_spelling_of_the_names(service):
    command = tools.update_spatial_design.func(
        state=state(),
        tool_call_id="c1",
        spaces=[{"name": " Lab ", "purpose": "p"}, {"name": "Lounge", "purpose": "p"}],
        relationships=[
            {"from_space": "lab", "to_space": "LOUNGE", "type": "separated", "description": ""}
        ],
    )

    updated = command.update["spatial_design"]
    assert updated.spaces[0].name == "Lab"
    assert (updated.relationships[0].from_space, updated.relationships[0].to_space) == (
        "Lab",
        "Lounge",
    )


def test_update_without_any_list_does_nothing(service):
    command = tools.update_spatial_design.func(state=state(), tool_call_id="c1")

    assert service.saved == [] and "spatial_design" not in command.update


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"spaces": [space("Lab"), space("lab")]}, "same name"),
        ({"spaces": [space("Lab")], "relationships": [link("Lab", "Nowhere")]}, "unknown space"),
        ({"spaces": [space("Lab")], "relationships": [link("Lab", "lab")]}, "linked to itself"),
    ],
)
def test_update_refuses_inconsistent_designs(service, kwargs, expected):
    command = tools.update_spatial_design.func(state=state(), tool_call_id="c1", **kwargs)

    assert expected in message(command)
    assert service.saved == [] and "spatial_design" not in command.update


def test_removing_a_space_used_by_a_relationship_asks_for_the_relationships_too(service):
    command = tools.update_spatial_design.func(
        state=state(DRAFT), tool_call_id="c1", spaces=[space("Lab")]
    )

    assert "unknown space 'Lounge'" in message(command)
    assert "Send the updated list of relationships too" in message(command)
    assert service.saved == []


# ---- validate_spatial_design


def test_validate_keeps_the_design_with_the_latest_picture(service):
    current_state = state(PICTURED)

    command = tools.validate_spatial_design.func(state=current_state, tool_call_id="c1")

    assert service.validated == [(current_state["session_id"], 4)]
    assert command.update["spatial_design"].is_validated is True
    assert "picture version 4" in message(command)


def test_validate_can_keep_an_earlier_picture(service):
    current_state = state(PICTURED)

    tools.validate_spatial_design.func(state=current_state, tool_call_id="c1", version=2)

    assert service.validated == [(current_state["session_id"], 2)]


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        (EMPTY, "at least 2 spaces"),
        (SpatialDesign([LAB], [], False, 4), "at least 2 spaces"),
        (SpatialDesign([LAB, LOUNGE], [], False, 4), "no relationship"),
        (DRAFT, "no picture"),
    ],
)
def test_validate_refuses_an_incomplete_design(service, design, expected):
    command = tools.validate_spatial_design.func(state=state(design), tool_call_id="c1")

    assert expected in message(command)
    assert service.validated == [] and "spatial_design" not in command.update


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SpatialDesignNotFoundError("none"), "no picture version 4"),
        (SpatialImageOutdatedError("old"), "changed after that picture"),
    ],
)
def test_validate_reports_what_the_database_refuses(monkeypatch, error, expected):
    monkeypatch.setattr(tools, "get_spatial_design_service", lambda: FakeSpatialService(error))

    command = tools.validate_spatial_design.func(state=state(PICTURED), tool_call_id="c1")

    assert expected in message(command)
    assert "spatial_design" not in command.update


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
    def __init__(self):
        self.variables = None

    def get(self, name, **variables):
        self.variables = variables
        return f"PROMPT {name}"


class FakeConcepts:
    """What the subgraph reads: the validated concept and the latest picture of step 3."""

    def __init__(self, image=None, picture=None):
        self.image = image
        self.picture = picture
        self.asked = None

    def get_validated_image(self, session_id):
        return self.image

    def get_concept_image(self, session_id, version=None, step=None):
        self.asked = (version, step)
        return self.picture


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1"}])


def run(llm, design=EMPTY, image=None, prompts=None, text="hello", picture=None):
    graph = SpatialDesignGraph(
        llm=llm,
        prompt_service=prompts or FakePrompts(),
        concept_service=FakeConcepts(image, picture),
    )
    return graph.graph.invoke(
        {
            "messages": [HumanMessage(text)],
            "session_id": uuid4(),
            "information": INFO,
            "concept_design": None,
            "spatial_design": design,
        }
    )


def test_agent_has_the_tools_to_draw_and_no_web_search(service):
    llm = FakeLLM(AIMessage(content="hi"))

    run(llm)

    assert llm.bound_tools == ["update_spatial_design", "generate_image", "validate_spatial_design"]
    assert llm.bind_kwargs == {"parallel_tool_calls": False}


def test_the_prompt_gets_the_information_the_draft_and_the_status(service):
    prompts = FakePrompts()

    run(FakeLLM(AIMessage(content="hi")), PICTURED, prompts=prompts)

    assert set(prompts.variables) == {"information", "spatial_design", "status"}
    assert '"user_type": "architects"' in prompts.variables["information"]
    assert '"name": "Lab"' in prompts.variables["spatial_design"]
    assert '"type": "visual_link"' in prompts.variables["spatial_design"]
    assert "is_validated" not in prompts.variables["spatial_design"]
    assert "latest_image_version" not in prompts.variables["spatial_design"]
    assert "2 space(s) and 1 relationship(s)" in prompts.variables["status"]
    assert "the latest is version 4" in prompts.variables["status"]


def test_agent_sees_the_validated_concept_image(service):
    image = base64.b64encode(b"png").decode()
    llm = FakeLLM(AIMessage(content="I read your concept like this."))

    run(llm, image=image, text="go")

    system, context, user = llm.calls[0]
    assert isinstance(system, SystemMessage)
    urls = [p["image_url"]["url"] for p in context.content if p["type"] == "image_url"]
    assert urls == [f"data:image/png;base64,{image}"]
    assert user.content == "go"


def test_agent_sees_the_latest_picture_of_its_step_after_the_concept(service):
    concept = base64.b64encode(b"concept").decode()
    picture = base64.b64encode(b"picture").decode()
    concepts = FakeConcepts(concept, ConceptImage(5, picture, "image/png", "p"))
    llm = FakeLLM(AIMessage(content="How does it look?"))
    graph = SpatialDesignGraph(llm=llm, prompt_service=FakePrompts(), concept_service=concepts)

    graph.graph.invoke(
        {
            "messages": [HumanMessage("go")],
            "session_id": uuid4(),
            "information": INFO,
            "concept_design": None,
            "spatial_design": PICTURED,
        }
    )

    context = llm.calls[0][1]
    urls = [p["image_url"]["url"] for p in context.content if p["type"] == "image_url"]
    assert urls == [f"data:image/png;base64,{concept}", f"data:image/png;base64,{picture}"]
    texts = [p["text"] for p in context.content if p["type"] == "text"]
    assert any("version 5" in t for t in texts)
    # Only the pictures made in step 3 count as the picture of this step.
    assert concepts.asked == (None, 3)


def test_agent_without_a_concept_image_sends_only_text(service):
    llm = FakeLLM(AIMessage(content="hi"))

    run(llm)

    assert [type(m) for m in llm.calls[0]] == [SystemMessage, HumanMessage]


def test_agent_records_the_first_draft_then_asks_its_first_question(service):
    llm = FakeLLM(
        tool_call(
            "update_spatial_design",
            spaces=[
                {"name": "Lab", "purpose": "build"},
                {"name": "Lounge", "purpose": "rest"},
            ],
            relationships=[
                {"from_space": "Lab", "to_space": "Lounge", "type": "adjacent", "description": ""}
            ],
        ),
        AIMessage(content="Here is a first draft. Who works alone?"),
    )

    result = run(llm)

    assert [s.name for s in result["spatial_design"].spaces] == ["Lab", "Lounge"]
    assert service.saved[0][1] == result["spatial_design"]
    assert result["messages"][-1].content == "Here is a first draft. Who works alone?"
    # The second model call already sees the recorded draft in its prompt.
    assert isinstance(llm.calls[1][-1], ToolMessage)


def test_agent_draws_the_organization_then_asks_for_feedback(service, monkeypatch):
    from fakes import FakeConceptService, FakeGenerator

    from backend.src.graph.tools.generate_image import tool as generate_tool

    concepts, generator = FakeConceptService(concept_b64="Y29uY2VwdA=="), FakeGenerator()
    monkeypatch.setattr(generate_tool, "get_concept_design_service", lambda: concepts)
    monkeypatch.setattr(generate_tool, "get_image_generator_service", lambda: generator)
    llm = FakeLLM(
        tool_call("generate_image", prompt="The Lab next to the Lounge"),
        AIMessage(content="Here is the picture. What would you change?"),
    )
    graph = SpatialDesignGraph(llm=llm, prompt_service=FakePrompts(), concept_service=concepts)

    result = graph.graph.invoke(
        {
            "messages": [HumanMessage("looks good, draw it")],
            "session_id": uuid4(),
            "information": INFO,
            "concept_design": ConceptDesign(3, 2, True),
            "spatial_design": DRAFT,
        }
    )

    assert concepts.added == [("The Lab next to the Lounge", 3)]
    assert result["spatial_design"].latest_image_version == 1
    assert result["spatial_design"].is_validated is False
    assert result["concept_design"].is_validated is True  # step 2 is not reopened
    assert result["messages"][-1].content == "Here is the picture. What would you change?"


def test_agent_stops_right_after_the_validation(service):
    # The next step speaks next: the agent must not be called again after the validation.
    llm = FakeLLM(tool_call("validate_spatial_design"))

    result = run(llm, PICTURED, text="yes, that's right")

    assert result["spatial_design"].is_validated is True
    assert isinstance(result["messages"][-1], ToolMessage)
    assert len(llm.calls) == 1


def test_agent_keeps_talking_when_the_validation_is_refused(service):
    llm = FakeLLM(tool_call("validate_spatial_design"), AIMessage(content="Let's draw it first."))

    result = run(llm, DRAFT, text="yes")

    assert result["spatial_design"].is_validated is False
    assert result["messages"][-1].content == "Let's draw it first."


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        (EMPTY, "none yet: record a first draft now"),
        (DRAFT, "2 space(s) and 1 relationship(s) saved"),
    ],
)
def test_status_tells_what_the_draft_holds(design, expected):
    assert expected in SpatialDesignGraph.status(design)
    assert "Pictures of the organization generated: none yet" in SpatialDesignGraph.status(design)
    assert "Validated by the user: no" in SpatialDesignGraph.status(design)
    assert "Validated by the user: yes" in SpatialDesignGraph.status(
        replace(design, is_validated=True)
    )


def test_the_graph_builds_its_services_lazily(monkeypatch):
    monkeypatch.setattr(graph_module, "get_prompt_service", lambda: "prompts")
    monkeypatch.setattr(graph_module, "get_concept_design_service", lambda: "concepts")
    graph = SpatialDesignGraph(llm=FakeLLM())

    assert (graph.prompt_service, graph.concept_service) == ("prompts", "concepts")


def test_shared_graph_is_cached():
    graph_module.get_spatial_design_graph.cache_clear()
    assert graph_module.get_spatial_design_graph() is graph_module.get_spatial_design_graph()


def test_status_tells_the_latest_picture():
    assert "generated: the latest is version 4" in SpatialDesignGraph.status(PICTURED)
