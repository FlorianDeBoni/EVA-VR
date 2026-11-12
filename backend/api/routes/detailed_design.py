from dataclasses import asdict, replace
from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.api.schemas import DetailedDesignResponse, ValidateDetailedDesignRequest
from backend.services.detailedDesignService import get_detailed_design_service
from backend.services.errors import (
    DetailedDesignNotFoundError,
    DetailedImageOutdatedError,
    SessionNotFoundError,
)
from backend.src.graph.tools.detailed_design.rules import validation_problem

router = APIRouter(prefix="/detailed-design", tags=["detailed design"])


@router.post("/{session_id}/validate", summary="Validate the final version of the room")
def validate(
    session_id: UUID, body: ValidateDetailedDesignRequest | None = None
) -> DetailedDesignResponse:
    """Accept a picture of the last step as the final design, without going through the chat.

    It is what the assistant's `validate_detailed_design` tool does, with the same rules: at
    least one piece of furniture, a picture, and a picture that still shows the details (409
    otherwise, with the reason). The details and the picture are then copied into the session
    as its final design. Returns the detailed design, now validated.
    """
    service = get_detailed_design_service()
    try:
        design = service.get_detailed_design(session_id)
        problem = validation_problem(design)
        if problem:
            raise HTTPException(status_code=409, detail=f"Cannot validate yet: {problem}")
        version = (body and body.version) or design.latest_image_version
        service.validate(session_id, version)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DetailedDesignNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"There is no picture version {version}."
        ) from exc
    except DetailedImageOutdatedError as exc:
        raise HTTPException(
            status_code=409,
            detail="The details changed after this picture: ask for a new picture first.",
        ) from exc
    return DetailedDesignResponse(**asdict(replace(design, is_validated=True)))
