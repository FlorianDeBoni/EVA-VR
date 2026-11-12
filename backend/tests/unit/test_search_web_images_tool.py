import base64
from uuid import uuid4

import pytest

from backend.src.graph.tools.concept_design.schemas import ConceptDesign
from backend.src.graph.tools.search_web_images import tool as tool_module
from backend.src.graph.tools.search_web_images.schemas import (
    DownloadedImage,
    ImageHit,
    RankedImage,
)
from backend.src.graph.tools.search_web_images.tool import search_web_images

NOTHING = ConceptDesign(reference_count=0, latest_version=None, is_validated=False)


def _ranked(n):
    hit = ImageHit(
        f"title{n}", f"http://img/{n}", "", f"http://page/{n}", 900, 900, "interior", 1.0
    )
    return RankedImage(hit=hit, score=1 - n / 10, reason=f"reason{n}")


class FakeFinder:
    def __init__(self, count=3):
        self.count = count
        self.seen = None

    def download(self, query, criteria, count):
        self.seen = (query, criteria, count)
        return [
            DownloadedImage(_ranked(n), f"file{n}".encode(), "image/jpeg")
            for n in range(1, self.count + 1)
        ]


class FakeConceptService:
    def __init__(self):
        self.stored = None

    def replace_reference_images(self, session_id, images):
        self.stored = (session_id, images)

    def get_concept_design(self, session_id):
        return ConceptDesign(len(self.stored[1]), None, False, references_revision=42)


@pytest.fixture
def finder(monkeypatch):
    fake = FakeFinder()
    monkeypatch.setattr(tool_module, "get_web_image_finder_service", lambda: fake)
    return fake


@pytest.fixture
def service(monkeypatch):
    fake = FakeConceptService()
    monkeypatch.setattr(tool_module, "get_concept_design_service", lambda: fake)
    return fake


def _state():
    return {"session_id": uuid4(), "concept_design": NOTHING}


def test_tool_schema_exposes_only_query_and_criteria_to_the_model():
    props = search_web_images.tool_call_schema.model_json_schema()["properties"]
    assert set(props) == {"query", "criteria"}


def test_tool_ranks_downloads_and_stores_three_references_as_base64(finder, service):
    state = _state()

    command = search_web_images.func(
        state=state, tool_call_id="c1", query="creative studio", criteria="interior"
    )

    assert finder.seen == ("creative studio", "interior", 3)
    session_id, images = service.stored
    assert session_id == state["session_id"]
    assert [i.position for i in images] == [1, 2, 3]
    assert [i.source_url for i in images] == [f"http://img/{n}" for n in (1, 2, 3)]
    assert images[0].page_url == "http://page/1" and images[0].mime_type == "image/jpeg"
    assert base64.b64decode(images[0].image_b64) == b"file1"
    assert command.update["concept_design"] == ConceptDesign(3, None, False, 42)
    message = command.update["messages"][0]
    assert message.tool_call_id == "c1"
    assert "Reference 1: title1 (score 0.90, reason1)" in message.content


def test_tool_reports_when_nothing_is_usable(finder, service):
    finder.count = 0

    command = search_web_images.func(state=_state(), tool_call_id="c1", query="x")

    assert service.stored is None
    assert "concept_design" not in command.update
    assert "different keywords" in command.update["messages"][0].content
