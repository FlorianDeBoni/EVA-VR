from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from backend.infra.databaseClient import DatabaseClient
from backend.services import detailedDesignService as service_module
from backend.services.detailedDesignService import DetailedDesignService
from backend.services.errors import (
    DetailedDesignNotFoundError,
    DetailedImageOutdatedError,
    SessionNotFoundError,
)
from backend.src.graph.tools.detailed_design.schemas import Detail, DetailCategory, DetailedDesign

TABLE = Detail("Round table", DetailCategory.FURNITURE, "oak, 6 seats", "Lab", 2)
PALETTE = Detail("Palette", DetailCategory.COLOR, "white and sage")
DESIGN = DetailedDesign([TABLE, PALETTE], is_validated=False)
JSON = {
    "details": [
        {
            "name": "Round table",
            "category": "furniture",
            "description": "oak, 6 seats",
            "space": "Lab",
            "quantity": 2,
        },
        {
            "name": "Palette",
            "category": "color",
            "description": "white and sage",
            "space": None,
            "quantity": None,
        },
    ]
}


class FakeClient:
    """Stands in for DatabaseClient: records queries, answers with the rows in order."""

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


def test_get_detailed_design_rebuilds_the_dataclasses_from_json():
    row = {"design": JSON, "is_validated": True, "latest_image_version": 9}
    client = FakeClient(row)

    design = DetailedDesignService(client=client).get_detailed_design(uuid4())

    assert design == DetailedDesign([TABLE, PALETTE], is_validated=True, latest_image_version=9)
    assert design.details[0].category is DetailCategory.FURNITURE
    # The latest picture is the latest image made in step 4.
    assert "c.step = 4" in client.queries[0][0]


def test_a_session_without_draft_has_an_empty_design():
    row = {"design": None, "is_validated": False, "latest_image_version": None}

    design = DetailedDesignService(client=FakeClient(row)).get_detailed_design(uuid4())

    assert design == DetailedDesign([], False, None)


def test_get_detailed_design_of_an_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        DetailedDesignService(client=FakeClient(None)).get_detailed_design(uuid4())


def test_save_draft_upserts_the_json_and_reopens_the_validation():
    client = FakeClient()
    session_id = uuid4()

    DetailedDesignService(client=client).save_draft(session_id, DESIGN)

    sql, (saved_id, jsonb) = client.queries[0]
    assert "INSERT INTO detailed_design_drafts" in sql and "ON CONFLICT (session_id)" in sql
    assert saved_id == session_id
    assert jsonb.obj == JSON  # the flag and the picture version are not part of the design
    update = client.queries[1][0]
    assert "detailed_design = NULL" in update and "final_image = NULL" in update
    assert "detailed_design_validated = FALSE" in update


def test_saving_a_draft_for_an_unknown_session_raises():
    client = FakeClient(error=psycopg.errors.ForeignKeyViolation())

    with pytest.raises(SessionNotFoundError):
        DetailedDesignService(client=client).save_draft(uuid4(), DESIGN)


def test_validate_copies_the_draft_and_the_picture_into_the_main_table():
    client = FakeClient(rows=[{"outdated": False}, None])
    session_id = uuid4()

    DetailedDesignService(client=client).validate(session_id, 6)

    check, check_params = client.queries[0]
    assert "FROM detailed_design_drafts d, concept_images c" in check and "c.step = 4" in check
    assert check_params == (session_id, 6)
    update, params = client.queries[1]
    assert "detailed_design = d.design" in update and "final_image = c.image_b64" in update
    assert "detailed_design_validated = TRUE" in update and "c.step = 4" in update
    assert params == (session_id, 6)


def test_validating_without_a_draft_or_without_that_picture_raises():
    client = FakeClient(rows=[None])

    with pytest.raises(DetailedDesignNotFoundError):
        DetailedDesignService(client=client).validate(uuid4(), 6)
    assert len(client.queries) == 1  # nothing was written


def test_validating_a_picture_made_before_the_last_change_raises():
    client = FakeClient(rows=[{"outdated": True}])

    with pytest.raises(DetailedImageOutdatedError):
        DetailedDesignService(client=client).validate(uuid4(), 6)
    assert len(client.queries) == 1  # nothing was written


def test_client_is_built_lazily_from_env_and_cached(monkeypatch):
    built = []
    monkeypatch.setattr(
        DatabaseClient, "from_env", classmethod(lambda cls: built.append(1) or FakeClient())
    )
    service = DetailedDesignService()
    assert not built
    assert service.client is service.client
    assert len(built) == 1


def test_shared_service_is_cached():
    service_module.get_detailed_design_service.cache_clear()
    assert (
        service_module.get_detailed_design_service() is service_module.get_detailed_design_service()
    )
