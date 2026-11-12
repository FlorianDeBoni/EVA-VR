from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.infra import databaseClient as client_module
from backend.infra.databaseClient import DatabaseClient
from backend.services import databaseService as service_module
from backend.services.databaseService import DatabaseService
from backend.services.errors import SessionNotFoundError
from backend.src.graph.tools.gather_information.schemas import InformationToGather

ROW = {
    "user_type": "architect",
    "number_of_users": 5,
    "task_description": None,
    "goal": "g",
    "must_have_features": ["a", "b"],
    "is_validated": True,
}


class FakeClient:
    """Stands in for DatabaseClient: records queries and answers with `row`."""

    def __init__(self, row):
        self.queries = []
        self._row = row

    @contextmanager
    def connection(self):
        def execute(sql, params):
            self.queries.append((sql, params))
            return SimpleNamespace(fetchone=lambda: self._row)

        yield SimpleNamespace(execute=execute)


def test_get_information_reads_the_view_by_session_id():
    client = FakeClient(ROW)
    session_id = uuid4()

    info = DatabaseService(client=client).get_information(session_id)

    assert info == InformationToGather(**ROW)
    sql, params = client.queries[0]
    assert "FROM session_information" in sql
    assert params == (session_id,)


def test_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        DatabaseService(client=FakeClient(None)).get_information(uuid4())


def test_client_is_built_lazily_from_env_and_cached(monkeypatch):
    built = []
    monkeypatch.setattr(
        DatabaseClient, "from_env", classmethod(lambda cls: built.append(1) or FakeClient(ROW))
    )
    service = DatabaseService()
    assert not built
    assert service.client is service.client
    assert len(built) == 1


def test_shared_service_is_cached():
    service_module.get_database_service.cache_clear()
    assert service_module.get_database_service() is service_module.get_database_service()


def test_from_env_builds_conninfo(monkeypatch):
    for key, value in {
        "DB_HOST": "db.local",
        "DB_PORT": "5433",
        "DB_USER": "u",
        "DB_PASSWORD": "p w",
        "DB_NAME": "n",
    }.items():
        monkeypatch.setenv(key, value)

    info = DatabaseClient.from_env()._conninfo

    assert "host=db.local" in info
    assert "port=5433" in info
    assert "user=u" in info
    assert "password='p w'" in info
    assert "dbname=n" in info


def test_pool_opens_lazily_once_with_dict_rows(monkeypatch):
    created = []

    class FakePool:
        def __init__(self, conninfo, **kwargs):
            self.kwargs = kwargs
            self.opened = None
            self.closed = False
            created.append(self)

        def open(self, wait):
            self.opened = wait

        def close(self):
            self.closed = True

    monkeypatch.setattr(client_module, "ConnectionPool", FakePool)
    client = DatabaseClient("host=x")
    assert not created

    assert client.pool is client.pool
    assert len(created) == 1
    assert created[0].opened is True
    assert created[0].kwargs["open"] is False
    assert "row_factory" in created[0].kwargs["kwargs"]

    client.close()
    assert created[0].closed
    client.close()  # idempotent


EMPTY = InformationToGather(
    user_type="",
    number_of_users=None,
    task_description="",
    goal="",
    must_have_features=[],
    is_validated=False,
)


def test_create_session_inserts_empty_defaults_and_returns_id():
    new_id = uuid4()
    client = FakeClient({"id": new_id})

    assert DatabaseService(client=client).create_session() == new_id

    sql, params = client.queries[0]
    assert sql.startswith("INSERT INTO session")
    assert params == (None, "", None, "", "", [], False)


def test_session_exists_returns_the_flag():
    session_id = uuid4()
    client = FakeClient({"found": True})

    assert DatabaseService(client=client).session_exists(session_id) is True
    assert client.queries[0][1] == (session_id,)
    assert DatabaseService(client=FakeClient({"found": False})).session_exists(session_id) is False


def test_update_information_writes_all_fields_to_the_right_row():
    session_id = uuid4()
    client = FakeClient({"id": session_id})
    info = InformationToGather(**ROW)

    DatabaseService(client=client).update_information(session_id, info)

    sql, params = client.queries[0]
    assert sql.startswith("UPDATE session SET")
    assert "WHERE id = %s" in sql
    assert params == ("architect", 5, None, "g", ["a", "b"], True, session_id)


def test_update_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        DatabaseService(client=FakeClient(None)).update_information(uuid4(), EMPTY)


def test_create_session_keeps_the_given_id():
    given = uuid4()
    client = FakeClient({"id": given})

    assert DatabaseService(client=client).create_session(given) == given

    sql, params = client.queries[0]
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert params[0] == given


def test_create_session_with_an_id_that_already_exists_returns_it():
    given = uuid4()

    assert DatabaseService(client=FakeClient(None)).create_session(given) == given
