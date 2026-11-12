import base64
from dataclasses import replace
from uuid import UUID

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from openai import BadRequestError

from backend.services.conceptDesignService import get_concept_design_service
from backend.services.errors import ConceptImageNotFoundError
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    GenerateConceptImageInput,
    ValidateConceptInput,
)
from backend.src.graph.tools.generate_image.generate_image import get_image_generator_service
from backend.src.graph.tools.generate_image.schemas import GeneratedImage, ImageGenerationError
from backend.src.settings.LogManager import LogManager

logger = LogManager.get_logger(__name__)


def _result(tool_call_id: str, text: str, concept: ConceptDesign | None = None) -> Command:
    """Answer the model, and refresh the graph state's concept design when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if concept is not None:
        update["concept_design"] = concept
    return Command(update=update)


def _past_images(
    session_id: UUID, reference_numbers: list[int], base_version: int | None, limit: int
) -> tuple[list[tuple[str, GeneratedImage]], str | None]:
    """The images the new one is built from, labelled; or an error message for the model."""
    service = get_concept_design_service()
    past: list[tuple[str, GeneratedImage]] = []

    base = service.get_concept_image(session_id, base_version)
    if base is None and base_version is not None:
        return [], f"There is no concept version {base_version}."
    if base is not None:
        past.append(
            (
                f"the current concept (version {base.version}), to iterate on",
                GeneratedImage(base64.b64decode(base.image_b64), base.mime_type),
            )
        )

    references = {r.position: r for r in service.get_reference_images(session_id)}
    for number in dict.fromkeys(reference_numbers):
        reference = references.get(number)
        if reference is None:
            return [], f"There is no reference image {number}."
        past.append(
            (
                f"reference {number}, to take elements from",
                GeneratedImage(base64.b64decode(reference.image_b64), reference.mime_type),
            )
        )
    # The image to iterate on comes first, so it is the one kept when there are too many.
    return past[:limit], None


@tool("generate_concept_image", args_schema=GenerateConceptImageInput)
def generate_concept_image(
    state: dict,
    tool_call_id: str,
    prompt: str,
    reference_numbers: list[int] | None = None,
    base_version: int | None = None,
) -> Command:
    """Generate a concept image of the room's overall design and show it to the user.

    It iterates on the latest concept (or on `base_version`) and can take elements from the
    chosen reference images. Describe the whole design in `prompt`; when iterating, say what
    changes and what must stay. The result is saved as a new version.
    """
    session_id: UUID = state["session_id"]
    generator = get_image_generator_service()

    past, error = _past_images(
        session_id, reference_numbers or [], base_version, generator.max_past_images
    )
    if error:
        return _result(tool_call_id, error)

    full_prompt = prompt
    if past:
        inputs = "\n".join(f"Image {i}: {label}." for i, (label, _) in enumerate(past, start=1))
        full_prompt = f"Input images:\n{inputs}\n\n{prompt}"

    try:
        image = generator.generate(full_prompt, [image for _, image in past])
    except (ImageGenerationError, BadRequestError) as exc:
        logger.warning("Concept image generation failed: %s", exc)
        return _result(
            tool_call_id,
            "The image could not be generated (the request may have been refused). "
            "Try again with a simpler or rephrased description.",
        )

    concept: ConceptDesign = state["concept_design"]
    version = get_concept_design_service().add_concept_image(
        session_id, base64.b64encode(image.data).decode(), prompt
    )
    return _result(
        tool_call_id,
        f"Concept version {version} generated and shown to the user.",
        replace(concept, latest_version=version, is_validated=False),
    )


@tool("validate_concept", args_schema=ValidateConceptInput)
def validate_concept(state: dict, tool_call_id: str, version: int | None = None) -> Command:
    """Keep a concept image as the final concept of the room, as accepted by the user.

    Call it only after the user explicitly confirmed they are happy with that image. It
    refuses if no image was generated yet.
    """
    concept: ConceptDesign = state["concept_design"]
    version = version or concept.latest_version
    if version is None:
        return _result(tool_call_id, "Cannot validate yet: no concept image was generated.")

    try:
        get_concept_design_service().validate_concept(state["session_id"], version)
    except ConceptImageNotFoundError:
        return _result(tool_call_id, f"There is no concept version {version}.")
    return _result(
        tool_call_id, f"Concept version {version} validated.", replace(concept, is_validated=True)
    )
