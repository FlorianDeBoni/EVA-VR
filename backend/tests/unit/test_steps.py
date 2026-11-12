from dataclasses import replace

from backend.src.graph.steps import Step, current_step
from backend.src.graph.tools.concept_design.schemas import ConceptDesign
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.graph.tools.spatial_design.schemas import SpatialDesign

INFO = InformationToGather("a", 1, "t", "g", [], False)
CONCEPT = ConceptDesign(0, None, False)
SPATIAL = SpatialDesign([], [], False)


def _state(information=INFO, concept=CONCEPT, spatial=SPATIAL):
    return {"information": information, "concept_design": concept, "spatial_design": spatial}


def test_step_numbers_are_the_workshop_order():
    assert [int(step) for step in Step] == [1, 2, 3, 4]


def test_the_session_starts_at_step_1_until_the_information_is_validated():
    assert current_step(_state()) is Step.GATHER_INFORMATION


def test_validating_the_information_moves_to_step_2():
    validated = replace(INFO, is_validated=True)

    assert current_step(_state(validated)) is Step.CONCEPT_DESIGN


def test_validating_the_concept_moves_to_step_3():
    validated = replace(INFO, is_validated=True)
    concept = replace(CONCEPT, is_validated=True)

    assert current_step(_state(validated, concept)) is Step.SPATIAL_DESIGN


def test_validating_the_spatial_design_moves_to_step_4_and_it_stays_there():
    validated = replace(INFO, is_validated=True)
    concept = replace(CONCEPT, is_validated=True)
    spatial = replace(SPATIAL, is_validated=True)

    assert current_step(_state(validated, concept, spatial)) is Step.DETAILED_DESIGN


def test_a_validated_step_never_skips_an_earlier_one():
    validated_concept = replace(CONCEPT, is_validated=True)
    validated_spatial = replace(SPATIAL, is_validated=True)

    assert current_step(_state(INFO, validated_concept)) is Step.GATHER_INFORMATION
    assert current_step(_state(INFO, validated_concept, validated_spatial)) is (
        Step.GATHER_INFORMATION
    )
    assert current_step(_state(replace(INFO, is_validated=True), CONCEPT, validated_spatial)) is (
        Step.CONCEPT_DESIGN
    )
