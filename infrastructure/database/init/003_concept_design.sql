-- Step 2 (concept design). Safe to run again: `task dev:database` applies every script.

-- Main table: only the concept the user validated, with its flag.
ALTER TABLE session
    ADD COLUMN IF NOT EXISTS concept_image            TEXT,                        -- base64 of the validated image
    ADD COLUMN IF NOT EXISTS concept_design_validated BOOLEAN NOT NULL DEFAULT FALSE;

-- The 3 images found on the web, shown to the user to pick elements from (base64).
CREATE TABLE IF NOT EXISTS concept_reference_images (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    position    SMALLINT    NOT NULL CHECK (position > 0),   -- "Reference 1..3" shown to the user
    image_b64   TEXT        NOT NULL,
    mime_type   TEXT        NOT NULL,
    title       TEXT        NOT NULL DEFAULT '',
    source_url  TEXT        NOT NULL DEFAULT '',
    page_url    TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, position)
);

-- Every AI-generated concept image, kept so the next ones can iterate on them (base64).
CREATE TABLE IF NOT EXISTS concept_images (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    version     INTEGER     NOT NULL CHECK (version > 0),    -- 1, 2, 3... per session
    image_b64   TEXT        NOT NULL,
    mime_type   TEXT        NOT NULL DEFAULT 'image/png',
    prompt      TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, version)
);
