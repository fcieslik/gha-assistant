from collections.abc import Callable
from pathlib import Path

import pytest
from gitrepo import GitRepo


@pytest.fixture
def git_repo(tmp_path: Path) -> Callable[[str], GitRepo]:
    def create(name: str) -> GitRepo:
        path = tmp_path / name
        path.mkdir()
        repo = GitRepo(path)
        repo.git("init", "-b", "main")
        return repo

    return create
