import base64
from dataclasses import replace
from uuid import UUID

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from openai import BadRequestError

from backend.services.conceptDesignService import get_concept_design_service
from backend.src.graph.steps import Step, current_step
from backend.src.graph.tools.generate_image.generate_image import get_image_generator_service
from backend.src.graph.tools.generate_image.schemas import (
    GeneratedImage,
    GenerateImageInput,
    ImageGenerationError,
)
from backend.src.settings.LogManager import LogManager

logger = LogManager.get_logger(__name__)

# Every input image makes the generation slower, so a new picture is built from at most this
# many images, however many times the user iterates. In practice that is the latest picture, the
# validated concept (step 3) and the references (step 2): the history of older pictures is never
# sent. MAX_PAST_IMAGES can lower this limit, never raise it.
MAX_INPUT_IMAGES = 3

# The validated picture of the previous step that each later step refines, and how it is
# described to the model: (step that made it, label when it is the only base, label as anchor).
ANCHORS = {
    Step.SPATIAL_DESIGN: (
        Step.CONCEPT_DESIGN,
        "the validated concept, to refine by showing the spatial organization",
        "the validated concept, whose style, mood and materials must be kept",
    ),
    Step.DETAILED_DESIGN: (
        Step.SPATIAL_DESIGN,
        "the validated picture of the spatial organization, to refine by adding the details",
        "the validated picture of the spatial organization, whose layout, spaces and "
        "composition must be kept",
    ),
}


def _image(image_b64: str, mime_type: str) -> GeneratedImage:
    return GeneratedImage(base64.b64decode(image_b64), mime_type)


def _message(tool_call_id: str, text: str) -> ToolMessage:
    return ToolMessage(content=text, tool_call_id=tool_call_id)


def _tool_message(tool_call_id: str, text: str) -> Command:
    return Command(update={"messages": [_message(tool_call_id, text)]})


def _past_images(
    session_id: UUID,
    step: Step,
    reference_numbers: list[int],
    base_version: int | None,
    limit: int,
) -> tuple[list[tuple[str, GeneratedImage]], str | None]:
    """The images the new one is built from, labelled; or an error message for the model.

    In order of priority, because only `limit` of them are sent (generating takes longer with
    every image) and never the history of older pictures:
    1. the picture to iterate on: `base_version`, else the latest of the current step. In steps 3
       and 4 with none yet, it is the validated picture of the previous step that this step
       refines;
    2. in steps 3 and 4, that validated picture again, to keep what must not change (style and
       mood in step 3, layout in step 4);
    3. the web reference images the agent asked for.
    """
    service = get_concept_design_service()
    past: list[tuple[str, GeneratedImage]] = []

    base = service.get_concept_image(session_id, base_version, step=None if base_version else step)
    if base is None and base_version is not None:
        return [], f"There is no image version {base_version}."
    if base is not None:
        past.append(
            (
                f"the current picture (version {base.version}), to iterate on",
                _image(base.image_b64, base.mime_type),
            )
        )

    if step in ANCHORS:
        anchor_step, label_alone, label_anchor = ANCHORS[step]
        anchor_b64 = service.get_validated_image(session_id, step=anchor_step.value)
        if anchor_b64 is not None:
            past.append((label_anchor if past else label_alone, _image(anchor_b64, "image/png")))

    references = {r.position: r for r in service.get_reference_images(session_id)}
    for number in dict.fromkeys(reference_numbers):
        reference = references.get(number)
        if reference is None:
            return [], f"There is no reference image {number}."
        past.append(
            (
                f"reference {number}, to take elements from",
                _image(reference.image_b64, reference.mime_type),
            )
        )
    return past[:limit], None


@tool("generate_image", args_schema=GenerateImageInput)
def generate_image(
    state: dict,
    tool_call_id: str,
    prompt: str,
    reference_numbers: list[int] | None = None,
    base_version: int | None = None,
) -> Command:
    """Generate a picture of the room and show it to the user.

    It iterates on the latest picture of the current step (or on `base_version`) and can take
    elements from the chosen web reference images. Step 2 draws the concept of the room; step 3
    starts from the validated concept and shows the agreed spatial organization; step 4 starts
    from the validated spatial picture and adds the details. Describe the whole picture in
    `prompt`; when iterating, say what changes and what must stay. The result is saved as a
    new version.
    """
    session_id: UUID = state["session_id"]
    step = current_step(state)
    generator = get_image_generator_service()

    past, error = _past_images(
        session_id,
        step,
        reference_numbers or [],
        base_version,
        min(generator.max_past_images, MAX_INPUT_IMAGES),
    )
    if error:
        return _tool_message(tool_call_id, error)

    full_prompt = prompt
    if past:
        inputs = "\n".join(f"Image {i}: {label}." for i, (label, _) in enumerate(past, start=1))
        full_prompt = f"Input images:\n{inputs}\n\n{prompt}"

    try:
        image = generator.generate(full_prompt, [image for _, image in past])
    except (ImageGenerationError, BadRequestError) as exc:
        logger.warning("Image generation failed: %s", exc)
        return _tool_message(
            tool_call_id,
            "The image could not be generated (the request may have been refused). "
            "Try again with a simpler or rephrased description.",
        )

    version = get_concept_design_service().add_concept_image(
        session_id, base64.b64encode(image.data).decode(), prompt, step=step.value
    )
    # A new picture reopens the step that made it, and the progress follows the database.
    concept = state["concept_design"]
    update: dict = {"messages": [_message(tool_call_id, f"Version {version} generated and shown.")]}
    if step is Step.SPATIAL_DESIGN:
        update["concept_design"] = replace(concept, latest_version=version)
        update["spatial_design"] = replace(
            state["spatial_design"], latest_image_version=version, is_validated=False
        )
    elif step is Step.DETAILED_DESIGN:
        update["concept_design"] = replace(concept, latest_version=version)
        update["detailed_design"] = replace(
            state["detailed_design"], latest_image_version=version, is_validated=False
        )
    else:
        update["concept_design"] = replace(concept, latest_version=version, is_validated=False)
    return Command(update=update)
