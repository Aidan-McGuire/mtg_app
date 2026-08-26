import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
STAGE2_FILES = ("run_stage2.sh", "backlog_lib.py", "backlog_cli.py", "stage2_prompt.txt")


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


class Stage2Repo:
    def __init__(self, path, claude_log, env):
        self.path = path
        self.claude_log = claude_log
        self._env = env

    def run(self):
        return subprocess.run(
            ["bash", "scripts/run_stage2.sh"],
            cwd=self.path, env=self._env, capture_output=True, text=True,
        )

    def git(self, *args, check=True):
        return _git(self.path, *args, check=check)

    def write_item(self, id, title, priority="medium", status="queued", branch="", body="## Problem\n"):
        slug = title.lower().replace(" ", "-")
        backlog_dir = self.path / "docs" / "superpowers" / "backlog"
        backlog_dir.mkdir(parents=True, exist_ok=True)
        item_path = backlog_dir / f"{id:03d}-{slug}.md"
        item_path.write_text(
            f"---\nid: {id:03d}\ntitle: {title}\npriority: {priority}\n"
            f"status: {status}\nbranch: {branch}\ncreated: 2026-08-26\n---\n\n{body}"
        )
        return item_path


@pytest.fixture
def stage2_repo(tmp_path):
    """A real scratch git repo wired to run the real scripts/run_stage2.sh
    under test, with a stubbed `claude` binary standing in for the real CLI."""
    repo = (tmp_path / "repo").resolve()
    fakehome = (tmp_path / "fakehome").resolve()
    claude_log = (tmp_path / "claude.log").resolve()
    fakebin = (tmp_path / "fakebin").resolve()

    repo.mkdir()
    fakehome.mkdir()
    fakebin.mkdir()

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    for name in STAGE2_FILES:
        shutil.copy2(REPO_SCRIPTS / name, scripts_dir / name)

    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "stage2.settings.json").write_text("{}")

    claude_stub = fakebin / "claude"
    claude_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "claude invoked: $*" >> "{claude_log}"\n'
        "exit 0\n"
    )
    claude_stub.chmod(0o755)

    (repo / "README.md").write_text("scratch repo for run_stage2.sh tests\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    env = {
        **os.environ,
        "HOME": str(fakehome),
        "PATH": f"{fakebin}:{os.environ['PATH']}",
    }
    return Stage2Repo(repo, claude_log, env)


def test_fresh_claim_of_highest_priority_queued_item(stage2_repo):
    stage2_repo.write_item(1, "Sample Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")

    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert stage2_repo.claude_log.exists()
    assert "claude invoked" in stage2_repo.claude_log.read_text()

    branches = stage2_repo.git("branch", "--list", "item/1-sample-item").stdout
    assert "item/1-sample-item" in branches

    on_branch = stage2_repo.git(
        "show", "item/1-sample-item:docs/superpowers/backlog/001-sample-item.md"
    ).stdout
    assert "status: in-progress" in on_branch

    on_main = (stage2_repo.path / "docs/superpowers/backlog/001-sample-item.md").read_text()
    assert "status: queued" in on_main
