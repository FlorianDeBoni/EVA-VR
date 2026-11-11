import os
from pathlib import Path

from dotenv import dotenv_values

# pytest does not load .env.backend (only Taskfile does): load the template's
# settings so services and loggers created at import time can configure themselves.
_template = dotenv_values(Path(__file__).resolve().parents[2] / ".env.backend.template")
for _key in (
    "LOG_LEVEL",
    "LOG_FORMAT",
    "KEYWORD_WEIGHT",
    "CATEGORY_WEIGHT",
    "BLOCKED_HOSTS",
    "IMAGE_RANK_BATCH_SIZE",
    "IMAGE_SEARCH_TOP_K",
):
    os.environ.setdefault(_key, _template[_key])
