import base64

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from backend.services.conceptDesignService import get_concept_design_service
from backend.src.graph.tools.concept_design.schemas import ConceptDesign, ReferenceImage
from backend.src.graph.tools.search_web_images.finder import get_web_image_finder_service
from backend.src.graph.tools.search_web_images.schemas import SearchWebImagesInput

# Reference images found and shown to the user.
REFERENCE_COUNT = 3


def _result(tool_call_id: str, text: str, concept: ConceptDesign | None = None) -> Command:
    """Answer the model, and refresh the graph state's concept design when it changed."""
    update: dict = {"messages": [ToolMessage(content=text, tool_call_id=tool_call_id)]}
    if concept is not None:
        update["concept_design"] = concept
    return Command(update=update)


@tool("search_web_images", args_schema=SearchWebImagesInput)
def search_web_images(state: dict, tool_call_id: str, query: str, criteria: str = "") -> Command:
    """Search the web for images of spaces and show the 3 best ones to the user.

    Finds candidate images for the query, has a vision model rank them against the
    criteria, downloads the best ones and saves them as 'Reference 1' to 'Reference 3'.
    The user sees them right away and you see them in your next message. Calling it again
    replaces the previous references.
    """
    found = get_web_image_finder_service().download(query, criteria, REFERENCE_COUNT)
    images = [
        ReferenceImage(
            position=position,
            image_b64=base64.b64encode(item.data).decode(),
            mime_type=item.mime_type,
            title=item.ranked.hit.title,
            source_url=item.ranked.hit.image_url,
            page_url=item.ranked.hit.page_url,
        )
        for position, item in enumerate(found, start=1)
    ]

    if not images:
        return _result(
            tool_call_id,
            "No usable image found for this query. Try again with different keywords.",
        )

    service = get_concept_design_service()
    service.replace_reference_images(state["session_id"], images)
    listing = "\n".join(
        f"Reference {i.position}: {i.title or 'untitled'} (score {item.ranked.score:.2f}, "
        f"{item.ranked.reason})"
        for i, item in zip(images, found, strict=True)
    )
    return _result(
        tool_call_id,
        f"Found {len(images)} reference images, now shown to the user:\n{listing}",
        service.get_concept_design(state["session_id"]),
    )
