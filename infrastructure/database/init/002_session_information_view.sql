-- Read-side projection of `session`: exactly the fields of InformationToGather,
-- keyed by session_id. The backend reads sessions through this view.

CREATE OR REPLACE VIEW session_information AS
SELECT
    id AS session_id,
    user_type,
    number_of_users,
    task_description,
    goal,
    must_have_features,
    is_validated
FROM session;
