from backend.scripts import seed_prompts


class FakePromptService:
    def __init__(self):
        self.seeded = None

    def seed(self, prompts_dir):
        self.seeded = prompts_dir
        return {"hello": "created", "bye": "unchanged"}


def test_main_seeds_the_given_folder_and_prints_each_status(tmp_path, monkeypatch, capsys):
    service = FakePromptService()
    monkeypatch.setattr(seed_prompts, "get_prompt_service", lambda: service)

    assert seed_prompts.main([str(tmp_path)]) == 0

    assert service.seeded == tmp_path
    assert capsys.readouterr().out.splitlines() == ["hello: created", "bye: unchanged"]


def test_main_without_exactly_one_argument_prints_usage(capsys):
    assert seed_prompts.main([]) == 2
    assert seed_prompts.main(["a", "b"]) == 2
    assert "Usage" in capsys.readouterr().out


def test_main_rejects_a_missing_folder(tmp_path, monkeypatch, capsys):
    service = FakePromptService()
    monkeypatch.setattr(seed_prompts, "get_prompt_service", lambda: service)

    assert seed_prompts.main([str(tmp_path / "nope")]) == 1

    assert service.seeded is None
    assert "not a directory" in capsys.readouterr().out
