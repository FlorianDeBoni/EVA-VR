-- Step 3 (spatial design). Safe to run again: `task dev:database` applies every script.

-- Main table: only the spatial design the user validated, with its flag.
-- JSON shape: {"spaces": [...], "relationships": [...]} (see SpatialDesign in the backend).
ALTER TABLE session
    ADD COLUMN IF NOT EXISTS spatial_design           JSONB,
    ADD COLUMN IF NOT EXISTS spatial_design_validated BOOLEAN NOT NULL DEFAULT FALSE;

-- The working draft, one per session: what the assistant refines with the user.
CREATE TABLE IF NOT EXISTS spatial_design_drafts (
    session_id  UUID        PRIMARY KEY REFERENCES session(id) ON DELETE CASCADE,
    design      JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
