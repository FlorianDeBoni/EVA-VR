from dataclasses import asdict
from functools import lru_cache
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from backend.infra.databaseClient import DatabaseClient
from backend.services.errors import (
    SessionNotFoundError,
    SpatialDesignNotFoundError,
    SpatialImageOutdatedError,
)
from backend.src.graph.tools.spatial_design.schemas import (
    Relationship,
    RelationType,
    Space,
    SpatialDesign,
)
from backend.src.settings.LogManager import LogManager


class SpatialDesignService:
    """Reads and writes the spatial design of a session.

        service = get_spatial_design_service()
        service.save_draft(session_id, design)    # the working draft
        service.validate(session_id, version)     # the user accepted it, with picture `version`

    Like the concept design: the working draft lives in `spatial_design_drafts` (one per
    session) and only the validated design is copied into the `session` row, with its
    picture (`spatial_image`, base64) and the flag `spatial_design_validated`. The design is
    stored as JSON. The pictures are rows of `concept_images` made in step 3. The DatabaseClient is
    created lazily from the env.
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
    def _to_json(design: SpatialDesign) -> Jsonb:
        data = asdict(design)
        del data["is_validated"], data["latest_image_version"]
        return Jsonb(data)

    @staticmethod
    def _from_json(
        data: dict | None, is_validated: bool, latest_image_version: int | None = None
    ) -> SpatialDesign:
        data = data or {}
        return SpatialDesign(
            spaces=[Space(**space) for space in data.get("spaces", [])],
            relationships=[
                Relationship(**{**item, "type": RelationType(item["type"])})
                for item in data.get("relationships", [])
            ],
            is_validated=is_validated,
            latest_image_version=latest_image_version,
        )

    def get_spatial_design(self, session_id: UUID) -> SpatialDesign:
        """Return the working draft of a session (empty if none), its flag and latest picture.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT d.design, s.spatial_design_validated AS is_validated,"
                " (SELECT max(c.version) FROM concept_images c"
                "   WHERE c.session_id = s.id AND c.step = 3) AS latest_image_version"
                " FROM session s LEFT JOIN spatial_design_drafts d ON d.session_id = s.id"
                " WHERE s.id = %s",
                (session_id,),
            ).fetchone()
        if row is None:
            raise SessionNotFoundError(f"session {session_id} not found")
        return self._from_json(row["design"], row["is_validated"], row["latest_image_version"])

    def save_draft(self, session_id: UUID, design: SpatialDesign) -> None:
        """Replace the working draft. This reopens the step: the validated design is cleared.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        try:
            with self.client.connection() as conn:
                conn.execute(
                    "INSERT INTO spatial_design_drafts (session_id, design) VALUES (%s, %s)"
                    " ON CONFLICT (session_id)"
                    " DO UPDATE SET design = EXCLUDED.design, updated_at = now()",
                    (session_id, self._to_json(design)),
                )
                conn.execute(
                    "UPDATE session SET spatial_design = NULL, spatial_design_validated = FALSE"
                    " WHERE id = %s",
                    (session_id,),
                )
        except psycopg.errors.ForeignKeyViolation as exc:
            raise SessionNotFoundError(f"session {session_id} not found") from exc
        self.logger.info("Saved spatial design draft of session %s", session_id)

    def validate(self, session_id: UUID, version: int) -> None:
        """Copy the draft and the picture `version` into the session row, flagged validated.

        Raises:
            SpatialDesignNotFoundError: If the session has no draft, or no step-3 picture
                with this version.
            SpatialImageOutdatedError: If the draft was changed after that picture was made.
        """
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT d.updated_at > c.created_at AS outdated"
                " FROM spatial_design_drafts d, concept_images c"
                " WHERE d.session_id = %s AND c.session_id = d.session_id"
                " AND c.version = %s AND c.step = 3",
                (session_id, version),
            ).fetchone()
            if row is None:
                raise SpatialDesignNotFoundError(
                    f"session {session_id} has no spatial design draft or no picture v{version}"
                )
            if row["outdated"]:
                raise SpatialImageOutdatedError(
                    f"the spatial design of session {session_id} changed after picture v{version}"
                )
            conn.execute(
                "UPDATE session s SET spatial_design = d.design, spatial_image = c.image_b64,"
                " spatial_design_validated = TRUE"
                " FROM spatial_design_drafts d, concept_images c"
                " WHERE s.id = %s AND d.session_id = s.id AND c.session_id = s.id"
                " AND c.version = %s AND c.step = 3",
                (session_id, version),
            )

    def get_validated_design(self, session_id: UUID) -> SpatialDesign | None:
        """Return the validated spatial design, or None until the user accepted one."""
        with self.client.connection() as conn:
            row = conn.execute(
                "SELECT spatial_design FROM session WHERE id = %s AND spatial_design_validated",
                (session_id,),
            ).fetchone()
        return self._from_json(row["spatial_design"], True) if row else None


@lru_cache(maxsize=1)
def get_spatial_design_service() -> SpatialDesignService:
    """Shared default service instance."""
    return SpatialDesignService()
