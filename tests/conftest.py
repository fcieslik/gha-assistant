from collections.abc import Callable
from pathlib import Path

import pytest
from fake_agent import FakeAgent
from fake_agent import install as install_fake_agent
from fake_github import FakeGitHub
from fake_github import install as install_fake_github
from gitrepo import GitRepo

from gha_assistant import agent


@pytest.fixture
def git_repo(tmp_path: Path) -> Callable[[str], GitRepo]:
    def create(name: str) -> GitRepo:
        path = tmp_path / name
        path.mkdir()
        repo = GitRepo(path)
        repo.git("init", "-b", "main")
        return repo

    return create


@pytest.fixture
def fake_github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    """GitHub boundary replaced by an in-memory fake, with a token in the environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    return install_fake_github(monkeypatch)


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK is never reached from a test unless the test puts `query` back itself:
    a forgotten fake must fail loudly, not quietly spend money when a key is set."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test reached the real Claude Agent SDK")

    monkeypatch.setattr(agent, "query", refuse)


@pytest.fixture(autouse=True)
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    """Agent boundary replaced by a recording fake that answers with one stub remark."""
    return install_fake_agent(monkeypatch)
