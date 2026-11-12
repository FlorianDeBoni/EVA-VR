from functools import lru_cache
from uuid import UUID

from backend.infra.databaseClient import DatabaseClient
from backend.services.errors import SessionNotFoundError
from backend.src.graph.tools.gather_information.schemas import InformationToGather
from backend.src.settings.LogManager import LogManager


class DatabaseService:
    """Read access to the information gathered during sessions.

        info = get_database_service().get_information(session_id)

    Reads go through the `session_information` view, which exposes exactly the
    InformationToGather fields. The DatabaseClient is created lazily from the env.
    """

    def __init__(self, client: DatabaseClient | None = None) -> None:
        self._client = client
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> DatabaseClient:
        if self._client is None:
            self._client = DatabaseClient.from_env()
        return self._client

    def create_session(self, session_id: UUID | None = None) -> UUID:
        """Create an empty session and return its id.

        Starts from empty strings, no number of users, no features and not validated.
        The id is generated unless `session_id` is given; if a session with that id
        already exists (e.g. two concurrent first requests), it is left untouched.
        """
        empty = InformationToGather(
            user_type="",
            number_of_users=None,
            task_description="",
            goal="",
            must_have_features=[],
            is_validated=False,
        )
        with self.client.connection() as conn:
            row = conn.execute(
                "INSERT INTO session (id, user_type, number_of_users, task_description, goal,"
                " must_have_features, is_validated)"
                " VALUES (COALESCE(%s::uuid, gen_random_uuid()), %s, %s, %s, %s, %s::text[], %s)"
                " ON CONFLICT (id) DO NOTHING RETURNING id",
                (session_id, *self._values(empty)),
            ).fetchone()

        if row is None:
            return session_id
        self.logger.info("Created session %s", row["id"])
        return row["id"]

    def session_exists(self, session_id: UUID) -> bool:
        """Return whether a session with this id exists."""
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM session WHERE id = %s) AS found",
                (session_id,),
            ).fetchone()
        return row["found"]

    def update_information(self, session_id: UUID, information: InformationToGather) -> None:
        """Overwrite the gathered information of a session.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "UPDATE session SET user_type = %s, number_of_users = %s,"
                " task_description = %s, goal = %s, must_have_features = %s::text[],"
                " is_validated = %s WHERE id = %s RETURNING id",
                (*self._values(information), session_id),
            ).fetchone()

        if row is None:
            self.logger.info("Session %s not found", session_id)
            raise SessionNotFoundError(f"session {session_id} not found")

    @staticmethod
    def _values(information: InformationToGather) -> tuple:
        """InformationToGather fields in column order, as SQL parameters."""
        return (
            information.user_type,
            information.number_of_users,
            information.task_description,
            information.goal,
            information.must_have_features,
            information.is_validated,
        )

    def get_information(self, session_id: UUID) -> InformationToGather:
        """Return the InformationToGather of a session.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT user_type, number_of_users, task_description, goal,"
                " must_have_features, is_validated"
                " FROM session_information WHERE session_id = %s",
                (session_id,),
            ).fetchone()

        if row is None:
            self.logger.info("Session %s not found", session_id)
            raise SessionNotFoundError(f"session {session_id} not found")
        return InformationToGather(**row)


@lru_cache(maxsize=1)
def get_database_service() -> DatabaseService:
    """Shared default service instance."""
    return DatabaseService()
