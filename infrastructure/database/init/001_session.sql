-- Information gathered from the user during a session (mirrors InformationToGather).
-- Every init script can be run again safely: `task dev:database` re-applies them all.
-- Docker itself runs them once, when the database volume is first created.

CREATE TABLE IF NOT EXISTS session (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Gathered progressively during the conversation, so unknown until answered.
    user_type         TEXT,
    number_of_users   INTEGER     CHECK (number_of_users > 0),
    task_description  TEXT,
    goal              TEXT,
    must_have_features TEXT[]     NOT NULL DEFAULT '{}',

    is_validated      BOOLEAN     NOT NULL DEFAULT FALSE
);

-- Keep updated_at current on every UPDATE, whichever client writes.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER session_set_updated_at
    BEFORE UPDATE ON session
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
