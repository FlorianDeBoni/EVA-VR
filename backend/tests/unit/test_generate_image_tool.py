from uuid import uuid4

import httpx
import pytest
from fakes import FakeConceptService, FakeGenerator, ImageGenerationError, b64, reference
from openai import BadRequestError

from backend.src.graph.steps import Step, current_step
from backend.src.graph.tools.concept_design.schemas import ConceptDesign, ConceptImage
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.generate_image import tool as tool_module
from backend.src.graph.tools.generate_image.tool import generate_image
from backend.src.graph.tools.spatial_design.schemas import SpatialDesign

INFO = InformationToGather("architects", 5, "brainstorm", "find ideas", [], True)
NOTHING = ConceptDesign(reference_count=0, latest_version=None, is_validated=False)
EMPTY = SpatialDesign([], [], False)


@pytest.fixture
def service(monkeypatch):
    fake = FakeConceptService()
    monkeypatch.setattr(tool_module, "get_concept_design_service", lambda: fake)
    return fake


@pytest.fixture
def generator(monkeypatch, service):
    fake = FakeGenerator()
    monkeypatch.setattr(tool_module, "get_image_generator_service", lambda: fake)
    return fake


def step2(concept=NOTHING):
    """A session in step 2: the concept is not validated yet."""
    return {
        "session_id": uuid4(),
        "information": INFO,
        "concept_design": concept,
        "spatial_design": EMPTY,
    }


def step3(latest=None, picture=None):
    """A session in step 3: the concept was validated."""
    return {
        "session_id": uuid4(),
        "information": INFO,
        "concept_design": ConceptDesign(3, latest, True),
        "spatial_design": SpatialDesign([], [], False, latest_image_version=picture),
    }


def message(command):
    return command.update["messages"][0].content


def image(version, data):
    return ConceptImage(version, b64(data), "image/png", "p")


def test_the_model_only_sees_what_it_decides():
    props = generate_image.tool_call_schema.model_json_schema()["properties"]

    assert set(props) == {"prompt", "reference_numbers", "base_version"}


# ---- step 2: the concept


def test_first_generation_draws_from_the_chosen_references(service, generator):
    service.references = [reference(1), reference(2), reference(3)]
    state = step2(ConceptDesign(3, None, False))

    command = generate_image.func(
        state=state, tool_call_id="c1", prompt="A warm timber studio", reference_numbers=[3, 1, 3]
    )

    prompt, past = generator.calls[0]
    assert [i.data for i in past] == [b"ref\x03", b"ref\x01"]
    assert "Image 1: reference 3" in prompt and "Image 2: reference 1" in prompt
    assert prompt.endswith("A warm timber studio")
    assert service.added == [("A warm timber studio", 2)]
    assert command.update["concept_design"].latest_version == 1
    assert "spatial_design" not in command.update


def test_next_generations_iterate_on_the_latest_version_first(service, generator):
    service.references = [reference(1), reference(2), reference(3)]
    service.versions = [image(1, b"v1"), image(2, b"v2")]

    command = generate_image.func(
        state=step2(ConceptDesign(3, 2, False)),
        tool_call_id="c1",
        prompt="Make it brighter",
        reference_numbers=[1, 2, 3],
    )

    prompt, past = generator.calls[0]
    # Limit of 3 past images: the latest picture first, then the references, in order.
    assert [i.data for i in past] == [b"v2", b"ref\x01", b"ref\x02"]
    assert "Image 1: the current picture (version 2)" in prompt
    assert command.update["concept_design"] == ConceptDesign(3, 3, False)


def test_generation_can_go_back_to_an_earlier_version(service, generator):
    service.versions = [image(1, b"v1"), image(2, b"v2")]

    generate_image.func(
        state=step2(ConceptDesign(0, 2, False)), tool_call_id="c1", prompt="p", base_version=1
    )

    assert [i.data for i in generator.calls[0][1]] == [b"v1"]


def test_generation_without_any_past_image_sends_the_bare_prompt(service, generator):
    generate_image.func(state=step2(), tool_call_id="c1", prompt="a room")

    assert generator.calls == [("a room", [])]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [({"reference_numbers": [2]}, "reference image 2"), ({"base_version": 7}, "version 7")],
)
def test_generation_refuses_unknown_images(service, generator, kwargs, expected):
    command = generate_image.func(state=step2(), tool_call_id="c1", prompt="p", **kwargs)

    assert expected in message(command)
    assert generator.calls == [] and service.versions == []


def test_a_refused_or_empty_generation_is_reported_to_the_model(service, monkeypatch):
    request = httpx.Request("POST", "http://x")
    refused = BadRequestError("no", response=httpx.Response(400, request=request), body=None)
    for error in (ImageGenerationError("empty"), refused):
        monkeypatch.setattr(
            tool_module, "get_image_generator_service", lambda e=error: FakeGenerator(e)
        )

        command = generate_image.func(state=step2(), tool_call_id="c1", prompt="p")

        assert "could not be generated" in message(command)
        assert "concept_design" not in command.update
    assert service.versions == []


# ---- step 3: the refined picture


def test_the_state_tells_which_step_the_tool_works_for():
    assert current_step(step2()) is Step.CONCEPT_DESIGN
    assert current_step(step3()) is Step.SPATIAL_DESIGN


def test_the_first_picture_of_step_3_refines_the_validated_concept(service, generator):
    service.concept_b64 = b64(b"validated")
    # Step 2 made versions 1 and 2: they are not what step 3 iterates on.
    service.versions = [image(1, b"v1"), image(2, b"v2")]

    command = generate_image.func(
        state=step3(latest=2), tool_call_id="c1", prompt="Show the Lab next to the Lounge"
    )

    prompt, past = generator.calls[0]
    assert [i.data for i in past] == [b"validated"]
    assert "Image 1: the validated concept, to refine" in prompt
    assert service.added == [("Show the Lab next to the Lounge", 3)]
    update = command.update
    assert update["spatial_design"].latest_image_version == 3
    assert update["spatial_design"].is_validated is False
    # Step 2 stays validated: drawing in step 3 must not send the session back to step 2.
    assert update["concept_design"] == ConceptDesign(3, 3, True)


def test_next_pictures_iterate_on_the_latest_one_and_keep_the_concept_as_anchor(service, generator):
    service.concept_b64 = b64(b"validated")
    service.versions = [image(1, b"v1"), image(2, b"v2"), image(3, b"p1"), image(4, b"p2")]
    service.steps = {3: 3, 4: 3}

    command = generate_image.func(
        state=step3(latest=4, picture=4), tool_call_id="c1", prompt="Bigger lab"
    )

    prompt, past = generator.calls[0]
    assert [i.data for i in past] == [b"p2", b"validated"]
    assert "Image 1: the current picture (version 4)" in prompt
    assert "Image 2: the validated concept, whose style" in prompt
    assert command.update["spatial_design"].latest_image_version == 5
    assert service.added == [("Bigger lab", 3)]


def test_a_picture_can_go_back_to_any_earlier_version(service, generator):
    service.concept_b64 = b64(b"validated")
    service.versions = [image(1, b"v1"), image(2, b"p1"), image(3, b"p2")]
    service.steps = {2: 3, 3: 3}

    generate_image.func(
        state=step3(latest=3, picture=3), tool_call_id="c1", prompt="p", base_version=2
    )

    assert [i.data for i in generator.calls[0][1]] == [b"p1", b"validated"]


def test_step_3_without_a_validated_image_still_generates(service, generator):
    generate_image.func(state=step3(), tool_call_id="c1", prompt="a room")

    assert generator.calls == [("a room", [])]


def test_a_failed_picture_changes_nothing(service, monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "get_image_generator_service",
        lambda: FakeGenerator(ImageGenerationError("empty")),
    )

    command = generate_image.func(state=step3(), tool_call_id="c1", prompt="p")

    assert "spatial_design" not in command.update and service.versions == []


# ---- the number of images sent never grows


@pytest.mark.parametrize("make_state", [step2, step3], ids=["step 2", "step 3"])
def test_iterating_many_times_never_sends_more_than_three_images(service, generator, make_state):
    service.references = [reference(1), reference(2), reference(3)]
    service.concept_b64 = b64(b"validated")
    version, sent = None, []

    for _ in range(12):
        state = make_state()
        if version is not None:
            state["concept_design"] = ConceptDesign(
                3, version, state["concept_design"].is_validated
            )
            state["spatial_design"] = SpatialDesign([], [], False, latest_image_version=version)
        command = generate_image.func(
            state=state, tool_call_id="c1", prompt="again", reference_numbers=[1, 2, 3]
        )
        version = command.update["concept_design"].latest_version
        sent.append([i.data for i in generator.calls[-1][1]])

    assert len(service.versions) == 12
    assert all(len(images) <= 3 for images in sent)
    # Only the latest picture is sent, never the older ones.
    assert all(images.count(b"generated") <= 1 for images in sent)


def test_a_higher_limit_in_the_settings_cannot_raise_the_cap(service, generator):
    generator.max_past_images = 10
    service.references = [reference(1), reference(2), reference(3)]
    service.versions = [image(1, b"v1")]

    generate_image.func(
        state=step2(ConceptDesign(3, 1, False)),
        tool_call_id="c1",
        prompt="p",
        reference_numbers=[1, 2, 3],
    )

    assert len(generator.calls[0][1]) == tool_module.MAX_INPUT_IMAGES == 3


def test_a_lower_limit_in_the_settings_still_applies(service, generator):
    generator.max_past_images = 1
    service.concept_b64 = b64(b"validated")
    service.versions = [image(1, b"p1")]
    service.steps = {1: 3}

    generate_image.func(state=step3(latest=1, picture=1), tool_call_id="c1", prompt="p")

    # The picture to iterate on is the one kept; the concept anchor is dropped first.
    assert [i.data for i in generator.calls[0][1]] == [b"p1"]
