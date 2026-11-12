from dataclasses import asdict
from functools import lru_cache
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from backend.infra.databaseClient import DatabaseClient
from backend.services.errors import (
    DetailedDesignNotFoundError,
    DetailedImageOutdatedError,
    SessionNotFoundError,
)
from backend.src.graph.tools.detailed_design.schemas import Detail, DetailCategory, DetailedDesign
from backend.src.settings.LogManager import LogManager


class DetailedDesignService:
    """Reads and writes the detailed design of a session (the last step).

        service = get_detailed_design_service()
        service.save_draft(session_id, design)    # the working draft
        service.validate(session_id, version)     # the user accepted it, with picture `version`

    Same pattern as the spatial design: the working draft lives in `detailed_design_drafts`
    (one per session) and only the validated design is copied into the `session` row, with
    its picture (`final_image`, base64) and the flag `detailed_design_validated`. The
    design is stored as JSON. The pictures are rows of `concept_images` made in step 4.
    """

    def __init__(self, client: DatabaseClient | None = None) -> None:
        self._client = client
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> DatabaseClient:
        if self._client is None:
            self._client = DatabaseClient.from_env()
        return self._client

    @staticmethod
    def _to_json(design: DetailedDesign) -> Jsonb:
        return Jsonb({"details": [asdict(detail) for detail in design.details]})

    @staticmethod
    def _from_json(
        data: dict | None, is_validated: bool, latest_image_version: int | None
    ) -> DetailedDesign:
        details = [
            Detail(**{**item, "category": DetailCategory(item["category"])})
            for item in (data or {}).get("details", [])
        ]
        return DetailedDesign(details, is_validated, latest_image_version)

    def get_detailed_design(self, session_id: UUID) -> DetailedDesign:
        """Return the working draft of a session (empty if none), its flag and latest picture.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT d.design, s.detailed_design_validated AS is_validated,"
                " (SELECT max(c.version) FROM concept_images c"
                "   WHERE c.session_id = s.id AND c.step = 4) AS latest_image_version"
                " FROM session s LEFT JOIN detailed_design_drafts d ON d.session_id = s.id"
                " WHERE s.id = %s",
                (session_id,),
            ).fetchone()
        if row is None:
            raise SessionNotFoundError(f"session {session_id} not found")
        return self._from_json(row["design"], row["is_validated"], row["latest_image_version"])

    def save_draft(self, session_id: UUID, design: DetailedDesign) -> None:
        """Replace the working draft. This reopens the step: the validated design is cleared.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        try:
            with self.client.connection() as conn:
                conn.execute(
                    "INSERT INTO detailed_design_drafts (session_id, design) VALUES (%s, %s)"
                    " ON CONFLICT (session_id)"
                    " DO UPDATE SET design = EXCLUDED.design, updated_at = now()",
                    (session_id, self._to_json(design)),
                )
                conn.execute(
                    "UPDATE session SET detailed_design = NULL, final_image = NULL,"
                    " detailed_design_validated = FALSE WHERE id = %s",
                    (session_id,),
                )
        except psycopg.errors.ForeignKeyViolation as exc:
            raise SessionNotFoundError(f"session {session_id} not found") from exc
        self.logger.info("Saved detailed design draft of session %s", session_id)

    def validate(self, session_id: UUID, version: int) -> None:
        """Copy the draft and the picture `version` into the session row, flagged validated.

        Raises:
            DetailedDesignNotFoundError: If the session has no draft, or no step-4 picture
                with this version.
            DetailedImageOutdatedError: If the draft was changed after that picture was made.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT d.updated_at > c.created_at AS outdated"
                " FROM detailed_design_drafts d, concept_images c"
                " WHERE d.session_id = %s AND c.session_id = d.session_id"
                " AND c.version = %s AND c.step = 4",
                (session_id, version),
            ).fetchone()
            if row is None:
                raise DetailedDesignNotFoundError(
                    f"session {session_id} has no detailed design draft or no picture v{version}"
                )
            if row["outdated"]:
                raise DetailedImageOutdatedError(
                    f"the detailed design of session {session_id} changed after picture v{version}"
                )
            conn.execute(
                "UPDATE session s SET detailed_design = d.design, final_image = c.image_b64,"
                " detailed_design_validated = TRUE"
                " FROM detailed_design_drafts d, concept_images c"
                " WHERE s.id = %s AND d.session_id = s.id AND c.session_id = s.id"
                " AND c.version = %s AND c.step = 4",
                (session_id, version),
            )


@lru_cache(maxsize=1)
def get_detailed_design_service() -> DetailedDesignService:
    """Shared default service instance."""
    return DetailedDesignService()
