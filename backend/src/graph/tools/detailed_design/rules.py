from backend.src.graph.tools.detailed_design.schemas import DetailCategory, DetailedDesign

MIN_FURNITURE = 1


def validation_problem(design: DetailedDesign) -> str | None:
    """Why the detailed design cannot be validated yet, or None when it can.

    The one place for this rule: the assistant's `validate_detailed_design` tool and the
    "Validate final version" button of the frontend both go through it. (That the picture
    still shows the details is checked by the database, see `DetailedDesignService.validate`.)
    """
    furniture = [d for d in design.details if d.category is DetailCategory.FURNITURE]
    if len(furniture) < MIN_FURNITURE:
        return "no piece of furniture was recorded."
    if design.latest_image_version is None:
        return "no picture of the detailed design was generated. Generate one first."
    return None
