-- Step 3 ends with a picture of the spatial organization: a refined version of the concept.
-- Safe to run again: `task dev:database` applies every script.

-- The generated pictures of both steps live in concept_images; `step` tells which step made them.
ALTER TABLE concept_images
    ADD COLUMN IF NOT EXISTS step SMALLINT NOT NULL DEFAULT 2;

-- Main table: the picture the user validated together with the spatial design
-- (flag: spatial_design_validated, see 004).
ALTER TABLE session
    ADD COLUMN IF NOT EXISTS spatial_image TEXT;
