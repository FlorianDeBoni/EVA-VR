import logging

import pytest

from backend.src.settings.LogManager import LogManager


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "%(levelname)s %(message)s")
    monkeypatch.setattr(LogManager, "_configured", False)
    monkeypatch.setattr(LogManager, "_loggers", {})
    root = logging.getLogger()
    saved, level = list(root.handlers), root.level
    yield
    root.handlers[:] = saved
    root.setLevel(level)


def _ours():
    return [h for h in logging.getLogger().handlers if getattr(h, "_log_manager", False)]


def test_get_logger_is_cached_and_configures_once():
    a = LogManager.get_logger("x.y")
    b = LogManager.get_logger("x.y")
    LogManager.configure()
    assert a is b
    assert len(_ours()) == 1


def test_level_comes_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    LogManager.get_logger("a")
    assert logging.getLogger().level == logging.DEBUG


def test_force_reconfigure_replaces_handler():
    LogManager.configure("INFO")
    LogManager.configure("ERROR", force=True)
    assert len(_ours()) == 1
    assert logging.getLogger().level == logging.ERROR
