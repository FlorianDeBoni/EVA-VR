from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from backend.infra.databaseClient import DatabaseClient
from backend.services import spatialDesignService as service_module
from backend.services.errors import (
    SessionNotFoundError,
    SpatialDesignNotFoundError,
    SpatialImageOutdatedError,
)
from backend.services.spatialDesignService import SpatialDesignService
from backend.src.graph.tools.spatial_design.schemas import (
    Relationship,
    RelationType,
    Space,
    SpatialDesign,
)

DESIGN = SpatialDesign(
    spaces=[Space("Lab", "build", ["prototyping"], 4, "large"), Space("Lounge", "rest")],
    relationships=[Relationship("Lab", "Lounge", RelationType.VISUAL_LINK, "see each other")],
    is_validated=False,
)
JSON = {
    "spaces": [
        {
            "name": "Lab",
            "purpose": "build",
            "activities": ["prototyping"],
            "capacity": 4,
            "size": "large",
        },
        {"name": "Lounge", "purpose": "rest", "activities": [], "capacity": None, "size": None},
    ],
    "relationships": [
        {
            "from_space": "Lab",
            "to_space": "Lounge",
            "type": "visual_link",
            "description": "see each other",
        }
    ],
}


class FakeClient:
    """Stands in for DatabaseClient: records queries, answers with `row`."""

    def __init__(self, row=None, error=None, rows=None):
        self.queries = []
        self._row, self._error = row, error
        self._rows = list(rows) if rows is not None else None

    @contextmanager
    def connection(self):
        def execute(sql, params=None):
            if self._error:
                raise self._error
            self.queries.append((sql, params))
            row = self._rows.pop(0) if self._rows is not None else self._row
            return SimpleNamespace(fetchone=lambda: row)

        yield SimpleNamespace(execute=execute)


def test_get_spatial_design_rebuilds_the_dataclasses_from_json():
    row = {"design": JSON, "is_validated": True, "latest_image_version": 7}
    client = FakeClient(row)

    design = SpatialDesignService(client=client).get_spatial_design(uuid4())

    assert design == SpatialDesign(
        DESIGN.spaces, DESIGN.relationships, is_validated=True, latest_image_version=7
    )
    # The latest picture is the latest image made in step 3.
    assert "c.step = 3" in client.queries[0][0]
    assert design.relationships[0].type is RelationType.VISUAL_LINK


def test_a_session_without_draft_has_an_empty_design():
    row = {"design": None, "is_validated": False, "latest_image_version": None}

    design = SpatialDesignService(client=FakeClient(row)).get_spatial_design(uuid4())

    assert design == SpatialDesign([], [], False)


def test_get_spatial_design_of_an_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        SpatialDesignService(client=FakeClient(None)).get_spatial_design(uuid4())


def test_save_draft_upserts_the_json_and_reopens_the_validation():
    client = FakeClient()
    session_id = uuid4()

    SpatialDesignService(client=client).save_draft(session_id, DESIGN)

    sql, (saved_id, jsonb) = client.queries[0]
    assert "INSERT INTO spatial_design_drafts" in sql and "ON CONFLICT (session_id)" in sql
    assert saved_id == session_id
    assert jsonb.obj == JSON  # the flag and the picture version are not part of the design
    update = client.queries[1][0]
    assert "spatial_design = NULL" in update and "spatial_design_validated = FALSE" in update


def test_saving_a_draft_for_an_unknown_session_raises():
    client = FakeClient(error=psycopg.errors.ForeignKeyViolation())

    with pytest.raises(SessionNotFoundError):
        SpatialDesignService(client=client).save_draft(uuid4(), DESIGN)


def test_validate_copies_the_draft_and_the_picture_into_the_main_table():
    client = FakeClient(rows=[{"outdated": False}, None])
    session_id = uuid4()

    SpatialDesignService(client=client).validate(session_id, 6)

    check, check_params = client.queries[0]
    assert "FROM spatial_design_drafts d, concept_images c" in check and "c.step = 3" in check
    assert check_params == (session_id, 6)
    update, params = client.queries[1]
    assert "spatial_design = d.design" in update and "spatial_image = c.image_b64" in update
    assert "spatial_design_validated = TRUE" in update
    assert params == (session_id, 6)


def test_validating_without_a_draft_or_without_that_picture_raises():
    client = FakeClient(rows=[None])

    with pytest.raises(SpatialDesignNotFoundError):
        SpatialDesignService(client=client).validate(uuid4(), 6)
    assert len(client.queries) == 1  # nothing was written


def test_validating_a_picture_made_before_the_last_change_raises():
    client = FakeClient(rows=[{"outdated": True}])

    with pytest.raises(SpatialImageOutdatedError):
        SpatialDesignService(client=client).validate(uuid4(), 6)
    assert len(client.queries) == 1  # nothing was written


def test_get_validated_design():
    validated = SpatialDesignService(client=FakeClient({"spatial_design": JSON}))

    assert validated.get_validated_design(uuid4()) == SpatialDesign(
        DESIGN.spaces, DESIGN.relationships, True
    )
    assert SpatialDesignService(client=FakeClient(None)).get_validated_design(uuid4()) is None


def test_client_is_built_lazily_from_env_and_cached(monkeypatch):
    built = []
    monkeypatch.setattr(
        DatabaseClient, "from_env", classmethod(lambda cls: built.append(1) or FakeClient())
    )
    service = SpatialDesignService()
    assert not built
    assert service.client is service.client
    assert len(built) == 1


def test_shared_service_is_cached():
    service_module.get_spatial_design_service.cache_clear()
    assert (
        service_module.get_spatial_design_service() is service_module.get_spatial_design_service()
    )
