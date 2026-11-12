from functools import lru_cache
from uuid import UUID

import psycopg

from backend.infra.databaseClient import DatabaseClient
from backend.services.errors import ConceptImageNotFoundError, SessionNotFoundError
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ConceptImage,
    ReferenceImage,
)
from backend.src.settings.LogManager import LogManager


class ConceptDesignService:
    """Reads and writes what the concept design step produces.

        service = get_concept_design_service()
        version = service.add_concept_image(session_id, image_b64, prompt)
        service.validate_concept(session_id, version)

    Three places, all keyed by session:
    - `concept_reference_images`: the web images shown to the user,
    - `concept_images`: every AI-generated concept (the next ones iterate on them),
    - `session.concept_image` + `concept_design_validated`: only the validated one.
    Images are stored as base64 text. The DatabaseClient is created lazily from the env.
    """

    def __init__(self, client: DatabaseClient | None = None) -> None:
        self._client = client
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> DatabaseClient:
        if self._client is None:
            self._client = DatabaseClient.from_env()
        return self._client

    def get_concept_design(self, session_id: UUID) -> ConceptDesign:
        """Return the progress of the step.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT s.concept_design_validated AS is_validated,"
                " (SELECT count(*) FROM concept_reference_images r"
                "   WHERE r.session_id = s.id) AS reference_count,"
                " (SELECT (extract(epoch FROM max(r.created_at)) * 1000000)::bigint"
                "   FROM concept_reference_images r"
                "   WHERE r.session_id = s.id) AS references_revision,"
                " (SELECT max(c.version) FROM concept_images c"
                "   WHERE c.session_id = s.id) AS latest_version"
                " FROM session s WHERE s.id = %s",
                (session_id,),
            ).fetchone()
        if row is None:
            raise SessionNotFoundError(f"session {session_id} not found")
        return ConceptDesign(**row)

    # ----- reference images (found on the web)

    def replace_reference_images(self, session_id: UUID, images: list[ReferenceImage]) -> None:
        """Replace the reference images of a session by `images`.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        try:
            with self.client.connection() as conn:
                conn.execute(
                    "DELETE FROM concept_reference_images WHERE session_id = %s", (session_id,)
                )
                with conn.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO concept_reference_images (session_id, position, image_b64,"
                        " mime_type, title, source_url, page_url)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        [
                            (
                                session_id,
                                i.position,
                                i.image_b64,
                                i.mime_type,
                                i.title,
                                i.source_url,
                                i.page_url,
                            )
                            for i in images
                        ],
                    )
        except psycopg.errors.ForeignKeyViolation as exc:
            raise SessionNotFoundError(f"session {session_id} not found") from exc
        self.logger.info("Stored %d reference images for session %s", len(images), session_id)

    def get_reference_images(self, session_id: UUID) -> list[ReferenceImage]:
        """Return the reference images of a session, by position (empty if none)."""
        with self.client.connection() as conn:
            rows = conn.execute(
                "SELECT position, image_b64, mime_type, title, source_url, page_url"
                " FROM concept_reference_images WHERE session_id = %s ORDER BY position",
                (session_id,),
            ).fetchall()
        return [ReferenceImage(**row) for row in rows]

    def get_reference_image(self, session_id: UUID, position: int) -> ReferenceImage | None:
        """Return one reference image, or None."""
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT position, image_b64, mime_type, title, source_url, page_url"
                " FROM concept_reference_images WHERE session_id = %s AND position = %s",
                (session_id, position),
            ).fetchone()
        return ReferenceImage(**row) if row else None

    # ----- generated concept images

    def add_concept_image(self, session_id: UUID, image_b64: str, prompt: str) -> int:
        """Store a new generated image and return its version (1, 2, 3...).

        A new image reopens the step: the validated concept of the session is cleared.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        try:
            with self.client.connection() as conn:
                row = conn.execute(
                    "INSERT INTO concept_images (session_id, version, image_b64, prompt)"
                    " SELECT %s, COALESCE(MAX(version), 0) + 1, %s, %s"
                    " FROM concept_images WHERE session_id = %s RETURNING version",
                    (session_id, image_b64, prompt, session_id),
                ).fetchone()
                conn.execute(
                    "UPDATE session SET concept_image = NULL, concept_design_validated = FALSE"
                    " WHERE id = %s",
                    (session_id,),
                )
        except psycopg.errors.ForeignKeyViolation as exc:
            raise SessionNotFoundError(f"session {session_id} not found") from exc
        self.logger.info("Stored concept image v%d for session %s", row["version"], session_id)
        return row["version"]

    def get_concept_image(
        self, session_id: UUID, version: int | None = None
    ) -> ConceptImage | None:
        """Return the concept image of this version (the latest by default), or None."""
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT version, image_b64, mime_type, prompt FROM concept_images"
                " WHERE session_id = %s AND (%s::int IS NULL OR version = %s)"
                " ORDER BY version DESC LIMIT 1",
                (session_id, version, version),
            ).fetchone()
        return ConceptImage(**row) if row else None

    # ----- validated concept (main table)

    def validate_concept(self, session_id: UUID, version: int) -> None:
        """Keep the image of this version as the session's concept and flag it validated.

        Raises:
            ConceptImageNotFoundError: If the session has no image with this version.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "UPDATE session s SET concept_image = c.image_b64, concept_design_validated = TRUE"
                " FROM concept_images c"
                " WHERE s.id = %s AND c.session_id = s.id AND c.version = %s RETURNING s.id",
                (session_id, version),
            ).fetchone()
        if row is None:
            raise ConceptImageNotFoundError(f"session {session_id} has no concept image v{version}")

    def get_validated_image(self, session_id: UUID) -> str | None:
        """Return the base64 of the validated concept, or None."""
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT concept_image FROM session WHERE id = %s AND concept_design_validated",
                (session_id,),
            ).fetchone()
        return row["concept_image"] if row else None


@lru_cache(maxsize=1)
def get_concept_design_service() -> ConceptDesignService:
    """Shared default service instance."""
    return ConceptDesignService()
