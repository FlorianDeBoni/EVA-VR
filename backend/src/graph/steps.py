from enum import IntEnum

from backend.src.graph.state import GraphState


class Step(IntEnum):
    """The steps of the design workshop, in order. The value is the step number."""

    GATHER_INFORMATION = 1
    CONCEPT_DESIGN = 2
    SPATIAL_DESIGN = 3
    DETAILED_DESIGN = 4


def current_step(state: GraphState) -> Step:
    """The step the session is in, derived from what the user has validated so far.

    Derived, never stored, so it cannot drift from the validation flags. It moves forward
    as soon as the previous step is validated, in the very turn that validates it. The last
    step stays current once validated, until a next step exists.
    """
    if not state["information"].is_validated:
        return Step.GATHER_INFORMATION
    if not state["concept_design"].is_validated:
        return Step.CONCEPT_DESIGN
    if not state["spatial_design"].is_validated:
        return Step.SPATIAL_DESIGN
    return Step.DETAILED_DESIGN
