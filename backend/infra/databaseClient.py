from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class DatabaseClient:
    """Lazily creates and caches a connection pool to the application Postgres database.

        client = DatabaseClient.from_env()
        with client.connection() as conn:
            conn.execute("SELECT 1")

    Rows come back as dicts. The pool opens on first use, so building a client
    never touches the network.
    """

    def __init__(self, conninfo: str, **pool_options) -> None:
        self._conninfo = conninfo
        self._pool_options = pool_options
        self._pool: ConnectionPool | None = None
        self.logger = LogManager.get_logger(__name__)

    @classmethod
    def from_env(cls) -> DatabaseClient:
        """Build from DB_HOST, DB_PORT, DB_USER, DB_PASSWORD and DB_NAME (see .env.backend)."""
        conninfo = make_conninfo(
            host=EnvManager.get_env_variable(EnvKeyName.KEY_DB_HOST),
            port=EnvManager.get_env_variable(EnvKeyName.KEY_DB_PORT),
            user=EnvManager.get_env_variable(EnvKeyName.KEY_DB_USER),
            password=EnvManager.get_env_variable(EnvKeyName.KEY_DB_PASSWORD),
            dbname=EnvManager.get_env_variable(EnvKeyName.KEY_DB_NAME),
        )
        return cls(conninfo)

    @property
    def pool(self) -> ConnectionPool:
        """Return the (lazily created and opened, cached) pool."""
        if self._pool is None:
            self.logger.info("Opening database connection pool")
            pool = ConnectionPool(
                self._conninfo,
                open=False,
                kwargs={"row_factory": dict_row},
                **self._pool_options,
            )
            pool.open(wait=True)
            self._pool = pool
        return self._pool

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection]:
        """Borrow a connection; commits on success, rolls back on error, then returns it."""
        with self.pool.connection() as conn:
            yield conn

    def close(self) -> None:
        """Close the pool, if it was ever opened."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
