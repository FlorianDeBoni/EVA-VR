from dataclasses import replace

from backend.src.graph.steps import Step, current_step
from backend.src.graph.tools.concept_design.schemas import ConceptDesign
from backend.src.graph.tools.gather_information.schemas import InformationToGather

INFO = InformationToGather("a", 1, "t", "g", [], False)
CONCEPT = ConceptDesign(0, None, False)


def _state(information=INFO, concept=CONCEPT):
    return {"information": information, "concept_design": concept}


def test_step_numbers_are_the_workshop_order():
    assert [int(step) for step in Step] == [1, 2, 3]


def test_the_session_starts_at_step_1_until_the_information_is_validated():
    assert current_step(_state()) is Step.GATHER_INFORMATION


def test_validating_the_information_moves_to_step_2():
    validated = replace(INFO, is_validated=True)

    assert current_step(_state(validated)) is Step.CONCEPT_DESIGN


def test_validating_the_concept_moves_to_step_3_and_it_stays_there():
    validated = replace(INFO, is_validated=True)
    concept = replace(CONCEPT, is_validated=True)

    assert current_step(_state(validated, concept)) is Step.SPATIAL_DESIGN


def test_a_validated_concept_does_not_skip_the_information_step():
    assert (
        current_step(_state(INFO, replace(CONCEPT, is_validated=True))) is Step.GATHER_INFORMATION
    )
