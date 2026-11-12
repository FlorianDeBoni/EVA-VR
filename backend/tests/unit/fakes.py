"""Test doubles shared by several test files."""

import base64

from backend.services.errors import ConceptImageNotFoundError
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ConceptImage,
    ReferenceImage,
)
from backend.src.graph.tools.generate_image.schemas import GeneratedImage, ImageGenerationError


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def reference(position, data=b"ref"):
    return ReferenceImage(
        position, b64(data + bytes([position])), "image/jpeg", f"R{position}", "", ""
    )


class FakeConceptService:
    """In-memory ConceptDesignService.

    `versions` are the generated images; `steps` says which step made each version
    (step 2 unless told otherwise). `validated` is the validated concept version, or
    `concept_b64` can be set directly; `spatial_b64` and `final_b64` are the validated
    pictures of steps 3 and 4.
    """

    def __init__(
        self,
        references=(),
        versions=(),
        steps=None,
        concept_b64=None,
        spatial_b64=None,
        final_b64=None,
    ):
        self.references = list(references)
        self.versions = list(versions)
        self.steps = dict(steps or {})
        self.validated = None
        self.concept_b64 = concept_b64
        self.spatial_b64 = spatial_b64
        self.final_b64 = final_b64
        self.added = []

    def step_of(self, version):
        return self.steps.get(version, 2)

    def get_concept_design(self, session_id):
        return ConceptDesign(
            len(self.references),
            self.versions[-1].version if self.versions else None,
            self.validated is not None,
        )

    def replace_reference_images(self, session_id, images):
        self.references = list(images)

    def get_reference_images(self, session_id):
        return list(self.references)

    def get_reference_image(self, session_id, position):
        return next((r for r in self.references if r.position == position), None)

    def add_concept_image(self, session_id, image_b64, prompt, step=2):
        version = len(self.versions) + 1
        self.versions.append(ConceptImage(version, image_b64, "image/png", prompt))
        self.steps[version] = step
        self.added.append((prompt, step))
        if step == 2:
            self.validated = None
        return version

    def get_concept_image(self, session_id, version=None, step=None):
        candidates = [
            v
            for v in self.versions
            if (version is None or v.version == version)
            and (step is None or self.step_of(v.version) == step)
        ]
        return candidates[-1] if candidates else None

    def validate_concept(self, session_id, version):
        if self.get_concept_image(session_id, version) is None:
            raise ConceptImageNotFoundError("missing")
        self.validated = version

    def get_validated_image(self, session_id, step=2):
        if step == 3:
            return self.spatial_b64
        if step == 4:
            return self.final_b64
        if self.concept_b64 is not None:
            return self.concept_b64
        if self.validated is None:
            return None
        return self.get_concept_image(session_id, self.validated).image_b64


class FakeGenerator:
    """Stands in for ImageGeneratorService: records what it was asked to draw."""

    max_past_images = 3

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def generate(self, prompt, past_images=()):
        if self.error:
            raise self.error
        self.calls.append((prompt, list(past_images)))
        return GeneratedImage(b"generated", "image/png")


__all__ = ["FakeConceptService", "FakeGenerator", "ImageGenerationError", "b64", "reference"]
