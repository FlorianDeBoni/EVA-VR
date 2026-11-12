-- Step 4 (detailed design). Safe to run again: `task dev:database` applies every script.

-- Main table: only the detailed design the user validated, with its final picture and flag.
-- JSON shape: {"details": [...]} (see DetailedDesign in the backend).
ALTER TABLE session
    ADD COLUMN IF NOT EXISTS detailed_design           JSONB,
    ADD COLUMN IF NOT EXISTS final_image               TEXT,     -- base64 of the final picture
    ADD COLUMN IF NOT EXISTS detailed_design_validated BOOLEAN NOT NULL DEFAULT FALSE;

-- The working draft, one per session: what the assistant refines with the user.
-- The pictures of this step are rows of concept_images with step = 4.
CREATE TABLE IF NOT EXISTS detailed_design_drafts (
    session_id  UUID        PRIMARY KEY REFERENCES session(id) ON DELETE CASCADE,
    design      JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
