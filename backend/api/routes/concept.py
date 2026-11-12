import base64
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from backend.services.conceptDesignService import get_concept_design_service

router = APIRouter(prefix="/concept", tags=["concept"])

# References can be replaced by a new search, and the validated image by a new validation.
NO_CACHE = {"Cache-Control": "no-cache"}
# A generated version never changes.
IMMUTABLE = {"Cache-Control": "private, max-age=86400, immutable"}


def _image(image_b64: str | None, mime_type: str, headers: dict[str, str]) -> Response:
    if image_b64 is None:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(content=base64.b64decode(image_b64), media_type=mime_type, headers=headers)


@router.get("/{session_id}/references/{position}", summary="A reference image found on the web")
def reference_image(session_id: UUID, position: int) -> Response:
    """The reference image shown to the user as 'Reference <position>' (1 to 3)."""
    image = get_concept_design_service().get_reference_image(session_id, position)
    return _image(image and image.image_b64, image.mime_type if image else "", NO_CACHE)


@router.get("/{session_id}/images/{version}", summary="A generated concept image")
def concept_image(session_id: UUID, version: int) -> Response:
    """The AI-generated concept image of this version (1, 2, 3...)."""
    image = get_concept_design_service().get_concept_image(session_id, version)
    return _image(image and image.image_b64, image.mime_type if image else "", IMMUTABLE)


@router.get("/{session_id}/validated", summary="The concept validated by the user")
def validated_concept(session_id: UUID) -> Response:
    """The concept image the user accepted (404 until they did)."""
    return _image(
        get_concept_design_service().get_validated_image(session_id), "image/png", NO_CACHE
    )


@router.get("/{session_id}/spatial", summary="The spatial picture validated by the user")
def validated_spatial_picture(session_id: UUID) -> Response:
    """The picture of the spatial organization the user accepted in step 3 (404 until then)."""
    return _image(
        get_concept_design_service().get_validated_image(session_id, step=3),
        "image/png",
        NO_CACHE,
    )


@router.get("/{session_id}/final", summary="The final picture validated by the user")
def final_picture(session_id: UUID) -> Response:
    """The final picture of the detailed design the user accepted in step 4 (404 until then)."""
    return _image(
        get_concept_design_service().get_validated_image(session_id, step=4),
        "image/png",
        NO_CACHE,
    )
