"""backend/.env at start-up: a flag from the file arrives, a variable that is already set wins."""
from app.envfiles import env_files, load_env_files


def test_a_flag_from_the_file_arrives_and_the_environment_wins(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# local settings\n   MODEL_PROVIDER=foundry-agents\nTACTICS_ENABLED=1\nITG_LANGUAGES=nl,es,fr\n\n",
                   encoding="utf-8")
    agents = tmp_path / ".env.foundry-agents"
    agents.write_text("FOUNDRY_SCOUT_AGENT_VERSION=3\nTACTICS_ENABLED=0\n", encoding="utf-8")
    for key in ("MODEL_PROVIDER", "TACTICS_ENABLED", "FOUNDRY_SCOUT_AGENT_VERSION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ITG_LANGUAGES", "nl")                    # set in the shell: wins

    loaded = load_env_files([env, tmp_path / "missing.env", agents])   # a missing file is skipped

    import os
    assert os.environ["TACTICS_ENABLED"] == "1"                  # from .env (the first file wins over the second)
    assert os.environ["MODEL_PROVIDER"] == "foundry-agents"      # leading spaces are fine
    assert os.environ["FOUNDRY_SCOUT_AGENT_VERSION"] == "3"      # from .env.foundry-agents
    assert os.environ["ITG_LANGUAGES"] == "nl"
    assert loaded == ["MODEL_PROVIDER", "TACTICS_ENABLED", "FOUNDRY_SCOUT_AGENT_VERSION"]


def test_the_app_reads_both_files_and_the_tests_read_none(monkeypatch):
    assert env_files() == []                                     # tests/conftest.py: no local settings in the tests
    monkeypatch.delenv("ITG_ENV_FILES")
    assert [p.name for p in env_files()] == [".env", ".env.foundry-agents"]
