import base64
from dataclasses import replace
from uuid import uuid4

import pytest
from fakes import FakeConceptService, FakeGenerator
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.services.errors import DetailedDesignNotFoundError, DetailedImageOutdatedError
from backend.src.graph.subgraphs.detailed_design import graph as graph_module
from backend.src.graph.subgraphs.detailed_design.graph import DetailedDesignGraph
from backend.src.graph.tools.concept_design.schemas import ConceptDesign, ConceptImage
from backend.src.graph.tools.detailed_design import tool as tools
from backend.src.graph.tools.detailed_design.schemas import (
    Detail,
    DetailCategory,
    DetailedDesign,
    DetailInput,
)
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.generate_image import tool as generate_tool
from backend.src.graph.tools.spatial_design.schemas import (
    Relationship,
    RelationType,
    Space,
    SpatialDesign,
)

INFO = InformationToGather("architects", 5, "brainstorm", "find ideas", [], True)
SPATIAL = SpatialDesign(
    [Space("Lab", "build"), Space("Lounge", "rest")],
    [Relationship("Lab", "Lounge", RelationType.ADJACENT, "")],
    True,
    latest_image_version=3,
)
EMPTY = DetailedDesign([], False)
TABLE = Detail("Round table", DetailCategory.FURNITURE, "oak, 6 seats", "Lab", 2)
PALETTE = Detail("Palette", DetailCategory.COLOR, "white and sage")
DRAFT = DetailedDesign([TABLE, PALETTE], False)
PICTURED = replace(DRAFT, latest_image_version=6)


class FakeDetailedService:
    """In-memory DetailedDesignService."""

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
    fake = FakeDetailedService()
    monkeypatch.setattr(tools, "get_detailed_design_service", lambda: fake)
    return fake


def state(design=EMPTY):
    return {
        "session_id": uuid4(),
        "information": INFO,
        "concept_design": ConceptDesign(3, 2, True),
        "spatial_design": SPATIAL,
        "detailed_design": design,
    }


def detail(name, category=DetailCategory.FURNITURE, space="Lab", **kwargs):
    return DetailInput(
        name=name, category=category, description=f"{name} description", space=space, **kwargs
    )


def message(command):
    return command.update["messages"][0].content


# ---- update_detailed_design


def test_the_model_only_sees_the_list_of_details():
    props = tools.update_detailed_design.tool_call_schema.model_json_schema()["properties"]

    assert set(props) == {"details"}


def test_update_saves_the_draft_and_reopens_the_validation(service):
    current = replace(PICTURED, is_validated=True)

    command = tools.update_detailed_design.func(
        state=state(current),
        tool_call_id="c1",
        details=[detail("Round table", quantity=2), detail("Palette", DetailCategory.COLOR, None)],
    )

    updated = command.update["detailed_design"]
    assert [d.name for d in updated.details] == ["Round table", "Palette"]
    assert updated.details[0] == Detail(
        "Round table", DetailCategory.FURNITURE, "Round table description", "Lab", 2
    )
    assert updated.details[1].space is None
    assert updated.is_validated is False
    assert updated.latest_image_version == 6  # the latest picture is still the latest picture
    assert service.saved[0][1] == updated
    assert "2 details" in message(command)


def test_update_accepts_plain_dicts_and_fixes_the_spelling_of_the_space(service):
    command = tools.update_detailed_design.func(
        state=state(),
        tool_call_id="c1",
        details=[
            {"name": " Sofa ", "category": "furniture", "description": "felt", "space": "lounge"}
        ],
    )

    updated = command.update["detailed_design"].details[0]
    assert (updated.name, updated.space) == ("Sofa", "Lounge")


def test_update_can_empty_the_list(service):
    command = tools.update_detailed_design.func(state=state(DRAFT), tool_call_id="c1", details=[])

    assert command.update["detailed_design"].details == []
    assert service.saved[0][1].details == []


def test_the_same_name_in_two_spaces_is_fine(service):
    command = tools.update_detailed_design.func(
        state=state(),
        tool_call_id="c1",
        details=[detail("Chair", space="Lab"), detail("Chair", space="Lounge")],
    )

    assert len(command.update["detailed_design"].details) == 2


@pytest.mark.parametrize(
    ("details", "expected"),
    [
        ([detail("Desk", space="Garage")], "unknown space 'Garage'"),
        ([detail("Desk"), detail("desk", space="LAB")], "'desk' is listed twice"),
    ],
)
def test_update_refuses_inconsistent_details(service, details, expected):
    command = tools.update_detailed_design.func(state=state(), tool_call_id="c1", details=details)

    assert expected in message(command)
    assert "Spaces: Lab, Lounge" in message(command)
    assert service.saved == [] and "detailed_design" not in command.update


# ---- validate_detailed_design


def test_validate_keeps_the_details_with_the_latest_picture(service):
    current_state = state(PICTURED)

    command = tools.validate_detailed_design.func(state=current_state, tool_call_id="c1")

    assert service.validated == [(current_state["session_id"], 6)]
    assert command.update["detailed_design"].is_validated is True
    assert "picture version 6" in message(command)


def test_validate_can_keep_an_earlier_picture(service):
    current_state = state(PICTURED)

    tools.validate_detailed_design.func(state=current_state, tool_call_id="c1", version=4)

    assert service.validated == [(current_state["session_id"], 4)]


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        (EMPTY, "no piece of furniture"),
        (DetailedDesign([PALETTE], False, 6), "no piece of furniture"),
        (DRAFT, "no picture"),
    ],
)
def test_validate_refuses_an_incomplete_design(service, design, expected):
    command = tools.validate_detailed_design.func(state=state(design), tool_call_id="c1")

    assert expected in message(command)
    assert service.validated == [] and "detailed_design" not in command.update


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (DetailedDesignNotFoundError("none"), "no picture version 6"),
        (DetailedImageOutdatedError("old"), "changed after that picture"),
    ],
)
def test_validate_reports_what_the_database_refuses(monkeypatch, error, expected):
    monkeypatch.setattr(tools, "get_detailed_design_service", lambda: FakeDetailedService(error))

    command = tools.validate_detailed_design.func(state=state(PICTURED), tool_call_id="c1")

    assert expected in message(command)
    assert "detailed_design" not in command.update


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


class FakeImages:
    """What the subgraph reads: the validated spatial picture and the latest of step 4."""

    def __init__(self, spatial=None, picture=None):
        self.spatial = spatial
        self.picture = picture
        self.asked = []

    def get_validated_image(self, session_id, step=2):
        self.asked.append(("validated", step))
        return self.spatial

    def get_concept_image(self, session_id, version=None, step=None):
        self.asked.append(("latest", step))
        return self.picture


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1"}])


def run(llm, design=EMPTY, spatial=None, prompts=None, text="hello", picture=None, images=None):
    graph = DetailedDesignGraph(
        llm=llm,
        prompt_service=prompts or FakePrompts(),
        concept_service=images or FakeImages(spatial, picture),
    )
    return graph.graph.invoke({**state(design), "messages": [HumanMessage(text)]})


def test_agent_has_the_tools_to_detail_draw_and_validate(service):
    llm = FakeLLM(AIMessage(content="hi"))

    run(llm)

    assert llm.bound_tools == [
        "update_detailed_design",
        "generate_image",
        "validate_detailed_design",
    ]
    assert llm.bind_kwargs == {"parallel_tool_calls": False}


def test_the_prompt_gets_the_information_the_spaces_the_draft_and_the_status(service):
    prompts = FakePrompts()

    run(FakeLLM(AIMessage(content="hi")), PICTURED, prompts=prompts)

    assert set(prompts.variables) == {"information", "spatial_design", "detailed_design", "status"}
    assert '"user_type": "architects"' in prompts.variables["information"]
    assert '"name": "Lounge"' in prompts.variables["spatial_design"]
    assert "is_validated" not in prompts.variables["spatial_design"]
    assert '"name": "Round table"' in prompts.variables["detailed_design"]
    assert '"category": "furniture"' in prompts.variables["detailed_design"]
    assert "latest_image_version" not in prompts.variables["detailed_design"]
    assert "2 detail(s) saved" in prompts.variables["status"]
    assert "the latest is version 6" in prompts.variables["status"]


def test_agent_sees_the_validated_spatial_picture_then_its_own_latest_picture(service):
    spatial = base64.b64encode(b"spatial").decode()
    picture = base64.b64encode(b"picture").decode()
    images = FakeImages(spatial, ConceptImage(7, picture, "image/png", "p"))
    llm = FakeLLM(AIMessage(content="How does it look?"))

    run(llm, PICTURED, images=images, text="go")

    system, context, user = llm.calls[0]
    assert isinstance(system, SystemMessage) and user.content == "go"
    urls = [p["image_url"]["url"] for p in context.content if p["type"] == "image_url"]
    assert urls == [f"data:image/png;base64,{spatial}", f"data:image/png;base64,{picture}"]
    assert any("version 7" in p["text"] for p in context.content if p["type"] == "text")
    # The spatial picture is the one validated in step 3; the latest one is made in step 4.
    assert images.asked == [("validated", 3), ("latest", 4)]


def test_agent_without_any_image_sends_only_text(service):
    llm = FakeLLM(AIMessage(content="hi"))

    run(llm)

    assert [type(m) for m in llm.calls[0]] == [SystemMessage, HumanMessage]


def test_agent_records_the_first_draft_then_asks_its_first_question(service):
    llm = FakeLLM(
        tool_call(
            "update_detailed_design",
            details=[
                {
                    "name": "Round table",
                    "category": "furniture",
                    "description": "oak",
                    "space": "Lab",
                }
            ],
        ),
        AIMessage(content="Here is a first draft. Who works standing?"),
    )

    result = run(llm)

    assert [d.name for d in result["detailed_design"].details] == ["Round table"]
    assert service.saved[0][1] == result["detailed_design"]
    assert result["messages"][-1].content == "Here is a first draft. Who works standing?"
    assert isinstance(llm.calls[1][-1], ToolMessage)


def test_agent_draws_the_details_then_asks_for_feedback(service, monkeypatch):
    concepts, generator = (
        FakeConceptService(spatial_b64="c3BhdGlhbA=="),
        FakeGenerator(),
    )
    monkeypatch.setattr(generate_tool, "get_concept_design_service", lambda: concepts)
    monkeypatch.setattr(generate_tool, "get_image_generator_service", lambda: generator)
    llm = FakeLLM(
        tool_call("generate_image", prompt="Same room, with oak round tables"),
        AIMessage(content="Here is the final picture. What would you change?"),
    )

    result = run(llm, DRAFT, images=concepts, text="looks good, draw it")

    # The first picture refines the validated spatial picture; step 2 and 3 stay validated.
    prompt, past = generator.calls[0]
    assert [i.data for i in past] == [b"spatial"]
    assert "the validated picture of the spatial organization, to refine" in prompt
    assert concepts.added == [("Same room, with oak round tables", 4)]
    assert result["detailed_design"].latest_image_version == 1
    assert result["detailed_design"].is_validated is False
    assert result["concept_design"].is_validated is True
    assert result["spatial_design"].is_validated is True
    assert result["messages"][-1].content == "Here is the final picture. What would you change?"


def test_agent_validates_then_says_goodbye(service):
    llm = FakeLLM(
        tool_call("validate_detailed_design"), AIMessage(content="This is your final room!")
    )

    result = run(llm, PICTURED, text="perfect")

    assert result["detailed_design"].is_validated is True
    # It is the last step: nothing comes after it, so the assistant says goodbye itself.
    assert result["messages"][-1].content == "This is your final room!"


@pytest.mark.parametrize(
    ("design", "expected"),
    [
        (EMPTY, "none yet: record a first draft now"),
        (DRAFT, "2 detail(s) saved"),
    ],
)
def test_status_tells_what_the_draft_holds(design, expected):
    status = DetailedDesignGraph.status(design)

    assert expected in status
    assert "Pictures of the details generated: none yet" in status
    assert "Validated by the user: no" in status
    assert "Validated by the user: yes" in DetailedDesignGraph.status(
        replace(design, is_validated=True)
    )


def test_status_tells_the_latest_picture():
    assert "generated: the latest is version 6" in DetailedDesignGraph.status(PICTURED)


def test_the_graph_builds_its_services_lazily(monkeypatch):
    monkeypatch.setattr(graph_module, "get_prompt_service", lambda: "prompts")
    monkeypatch.setattr(graph_module, "get_concept_design_service", lambda: "concepts")
    graph = DetailedDesignGraph(llm=FakeLLM())

    assert (graph.prompt_service, graph.concept_service) == ("prompts", "concepts")


def test_shared_graph_is_cached():
    graph_module.get_detailed_design_graph.cache_clear()
    assert graph_module.get_detailed_design_graph() is graph_module.get_detailed_design_graph()
