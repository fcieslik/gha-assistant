import os
import subprocess
from pathlib import Path

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


class GitRepo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            check=True,
            capture_output=True,
            text=True,
            env=GIT_ENV,
        )
        return result.stdout.strip()

    def write(self, rel: str, text: str) -> None:
        file = self.path / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")
