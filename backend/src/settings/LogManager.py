import logging
import sys
from typing import ClassVar

from backend.src.settings.envManager import EnvKeyName, EnvManager


class LogManager:
    """Configures logging once and hands out cached loggers.

    Use it anywhere, no setup or object passing needed:

        logger = LogManager.get_logger(__name__)

    The first call configures the root logger (level and format from LOG_LEVEL / LOG_FORMAT in
    .env.backend). Later calls reuse the same handler and the same logger objects.
    """

    _configured: ClassVar[bool] = False
    _loggers: ClassVar[dict[str, logging.Logger]] = {}

    @classmethod
    def configure(
        cls,
        level: str | int | None = None,
        fmt: str | None = None,
        *,
        force: bool = False,
    ) -> None:
        """Set up the root logger. No-op if already configured unless `force=True`."""
        if cls._configured and not force:
            return

        if level is None:
            level = EnvManager.get_env_variable(EnvKeyName.KEY_LOG_LEVEL)
        if fmt is None:
            fmt = EnvManager.get_env_variable(EnvKeyName.KEY_LOG_FORMAT)
        if isinstance(level, str):
            level = level.upper()

        root = logging.getLogger()
        for handler in list(root.handlers):
            if getattr(handler, "_log_manager", False):
                root.removeHandler(handler)

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(fmt))
        handler._log_manager = True  # type: ignore[attr-defined]  # marks ours for reconfigure
        root.addHandler(handler)
        root.setLevel(level)
        cls._configured = True

    @classmethod
    def get_logger(cls, name: str | None = None) -> logging.Logger:
        """Return the cached logger for `name` (root logger when None), configuring first."""
        cls.configure()
        key = name or ""
        if key not in cls._loggers:
            cls._loggers[key] = logging.getLogger(name)
        return cls._loggers[key]

    @classmethod
    def set_level(cls, level: str | int, name: str | None = None) -> None:
        """Change the level of one logger (or the root logger) at runtime."""
        cls.get_logger(name).setLevel(level.upper() if isinstance(level, str) else level)
