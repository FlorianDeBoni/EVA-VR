from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from backend.services import conceptDesignService as service_module
from backend.services.conceptDesignService import ConceptDesignService
from backend.services.errors import ConceptImageNotFoundError, SessionNotFoundError
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ConceptImage,
    ReferenceImage,
)

REFERENCE = ReferenceImage(1, "QUJD", "image/jpeg", "title", "http://img", "http://page")


class FakeClient:
    """Stands in for DatabaseClient: records queries, answers with `row` / `rows`."""

    def __init__(self, row=None, rows=(), error=None):
        self.queries = []
        self.many = []
        self._row, self._rows, self._error = row, list(rows), error

    @contextmanager
    def connection(self):
        def execute(sql, params=None):
            if self._error:
                raise self._error
            self.queries.append((sql, params))
            return SimpleNamespace(fetchone=lambda: self._row, fetchall=lambda: self._rows)

        def cursor():
            @contextmanager
            def cm():
                yield SimpleNamespace(executemany=lambda sql, rows: self.many.append((sql, rows)))

            return cm()

        yield SimpleNamespace(execute=execute, cursor=cursor)


def test_get_concept_design_counts_references_and_versions():
    row = {
        "is_validated": True,
        "reference_count": 3,
        "latest_version": 2,
        "references_revision": 1_700_000_000_000_000,
    }
    session_id = uuid4()

    result = ConceptDesignService(client=FakeClient(row)).get_concept_design(session_id)

    assert result == ConceptDesign(
        reference_count=3,
        latest_version=2,
        is_validated=True,
        references_revision=1_700_000_000_000_000,
    )


def test_get_concept_design_of_an_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        ConceptDesignService(client=FakeClient(None)).get_concept_design(uuid4())


def test_replace_reference_images_deletes_then_inserts():
    client = FakeClient()
    session_id = uuid4()

    ConceptDesignService(client=client).replace_reference_images(session_id, [REFERENCE])

    assert "DELETE FROM concept_reference_images" in client.queries[0][0]
    sql, rows = client.many[0]
    assert "INSERT INTO concept_reference_images" in sql
    assert rows == [(session_id, 1, "QUJD", "image/jpeg", "title", "http://img", "http://page")]


def test_get_reference_images_maps_rows():
    row = {
        "position": 1,
        "image_b64": "QUJD",
        "mime_type": "image/jpeg",
        "title": "title",
        "source_url": "http://img",
        "page_url": "http://page",
    }

    service = ConceptDesignService(client=FakeClient(row=row, rows=[row]))

    assert service.get_reference_images(uuid4()) == [REFERENCE]
    assert service.get_reference_image(uuid4(), 1) == REFERENCE
    assert ConceptDesignService(client=FakeClient(None)).get_reference_image(uuid4(), 1) is None


def test_add_concept_image_returns_the_version_and_reopens_the_concept_validation():
    client = FakeClient(row={"version": 4})
    session_id = uuid4()

    version = ConceptDesignService(client=client).add_concept_image(session_id, "QUJD", "a prompt")

    assert version == 4
    assert "INSERT INTO concept_images" in client.queries[0][0]
    # Step 2 unless told otherwise.
    assert client.queries[0][1] == (session_id, "QUJD", "a prompt", 2, session_id)
    update = client.queries[1][0]
    assert "concept_image = NULL" in update and "concept_design_validated = FALSE" in update
    assert "spatial" not in update


def test_a_picture_of_step_3_reopens_the_spatial_design_not_the_concept():
    client = FakeClient(row={"version": 5})
    session_id = uuid4()

    ConceptDesignService(client=client).add_concept_image(session_id, "QUJD", "p", step=3)

    assert client.queries[0][1] == (session_id, "QUJD", "p", 3, session_id)
    update = client.queries[1][0]
    assert "spatial_image = NULL" in update and "spatial_design_validated = FALSE" in update
    # Step 2 stays validated: the session must not fall back to the concept step.
    assert "concept_design_validated" not in update and "concept_image" not in update


def test_adding_an_image_to_an_unknown_session_raises():
    client = FakeClient(error=psycopg.errors.ForeignKeyViolation())

    with pytest.raises(SessionNotFoundError):
        ConceptDesignService(client=client).add_concept_image(uuid4(), "QUJD", "p")


def test_get_concept_image_defaults_to_the_latest_version():
    row = {"version": 2, "image_b64": "QUJD", "mime_type": "image/png", "prompt": "p"}
    client = FakeClient(row)
    session_id = uuid4()

    image = ConceptDesignService(client=client).get_concept_image(session_id)

    assert image == ConceptImage(2, "QUJD", "image/png", "p")
    assert "ORDER BY version DESC LIMIT 1" in client.queries[0][0]
    assert client.queries[0][1] == (session_id, None, None, None, None)
    assert ConceptDesignService(client=FakeClient(None)).get_concept_image(uuid4(), 9) is None


def test_get_concept_image_can_be_limited_to_the_images_of_a_step():
    row = {"version": 5, "image_b64": "QUJD", "mime_type": "image/png", "prompt": "p"}
    client = FakeClient(row)
    session_id = uuid4()

    ConceptDesignService(client=client).get_concept_image(session_id, step=3)

    assert "step = %s" in client.queries[0][0]
    assert client.queries[0][1] == (session_id, None, None, 3, 3)


def test_validate_concept_copies_the_image_into_the_main_table():
    client = FakeClient(row={"id": 1})
    session_id = uuid4()

    ConceptDesignService(client=client).validate_concept(session_id, 2)

    sql, params = client.queries[0]
    assert "UPDATE session" in sql and "concept_design_validated = TRUE" in sql
    assert params == (session_id, 2)


def test_validating_a_missing_version_raises():
    with pytest.raises(ConceptImageNotFoundError):
        ConceptDesignService(client=FakeClient(None)).validate_concept(uuid4(), 2)


def test_get_validated_image_reads_the_column_of_the_step():
    client = FakeClient({"image": "QUJD"})
    service = ConceptDesignService(client=client)

    assert service.get_validated_image(uuid4()) == "QUJD"
    assert service.get_validated_image(uuid4(), step=3) == "QUJD"
    assert service.get_validated_image(uuid4(), step=4) == "QUJD"

    concept, spatial, final = (sql for sql, _ in client.queries)
    assert "concept_image AS image" in concept and "AND concept_design_validated" in concept
    assert "spatial_image AS image" in spatial and "AND spatial_design_validated" in spatial
    assert "final_image AS image" in final and "AND detailed_design_validated" in final
    assert ConceptDesignService(client=FakeClient(None)).get_validated_image(uuid4()) is None


def test_a_picture_of_step_4_reopens_the_detailed_design_only():
    client = FakeClient(row={"version": 8})
    session_id = uuid4()

    ConceptDesignService(client=client).add_concept_image(session_id, "QUJD", "p", step=4)

    assert client.queries[0][1] == (session_id, "QUJD", "p", 4, session_id)
    update = client.queries[1][0]
    assert "final_image = NULL" in update and "detailed_design_validated = FALSE" in update
    # The earlier steps stay validated: the session must not fall back to them.
    assert "concept" not in update and "spatial" not in update


def test_shared_service_is_cached():
    service_module.get_concept_design_service.cache_clear()
    assert (
        service_module.get_concept_design_service() is service_module.get_concept_design_service()
    )


def test_client_is_built_lazily_from_env_and_cached(monkeypatch):
    from backend.infra.databaseClient import DatabaseClient

    built = []
    monkeypatch.setattr(
        DatabaseClient, "from_env", classmethod(lambda cls: built.append(1) or FakeClient())
    )
    service = ConceptDesignService()
    assert not built
    assert service.client is service.client
    assert len(built) == 1


def test_replacing_references_of_an_unknown_session_raises():
    client = FakeClient(error=psycopg.errors.ForeignKeyViolation())

    with pytest.raises(SessionNotFoundError):
        ConceptDesignService(client=client).replace_reference_images(uuid4(), [REFERENCE])
