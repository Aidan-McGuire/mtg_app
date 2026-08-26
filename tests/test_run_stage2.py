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


def test_nothing_actionable_exits_zero_with_no_side_effects(stage2_repo):
    stage2_repo.write_item(1, "Accepted Already", priority="high", status="accepted")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add accepted item")

    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert not stage2_repo.claude_log.exists()
    assert stage2_repo.git("branch", "--list", "item/*").stdout.strip() == ""


def test_resumes_in_progress_branch_instead_of_selecting_a_new_item(stage2_repo):
    # First firing claims item 1.
    stage2_repo.write_item(1, "First Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    first = stage2_repo.run()
    assert first.returncode == 0, first.stderr

    # A second, higher-priority item appears on main before the first firing's
    # work is finished — the resume scan must still win over item 2's select.
    stage2_repo.write_item(2, "Second Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 2")

    stage2_repo.claude_log.unlink()
    second = stage2_repo.run()
    assert second.returncode == 0, second.stderr
    assert "claude invoked" in stage2_repo.claude_log.read_text()

    # Item 2 was never touched.
    assert stage2_repo.git("branch", "--list", "item/2-*").stdout.strip() == ""
    on_branch_1 = stage2_repo.git(
        "show", "item/1-first-item:docs/superpowers/backlog/001-first-item.md"
    ).stdout
    assert "status: in-progress" in on_branch_1


def test_finished_branch_awaiting_review_is_skipped_for_next_queued_item(stage2_repo):
    # Simulate a finished-and-pushed item 1 (in-review on its branch, main
    # still says queued) sitting untouched, and a queued item 2.
    stage2_repo.write_item(1, "Finished Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # claims item 1, branch item/1-finished-item now in-progress
    # Branch item/1-finished-item is checked out in its own worktree by the run
    # above — edit and commit there rather than `git checkout` it in the main
    # checkout (git refuses to check out a branch already held by a worktree).
    worktree = stage2_repo.path / ".claude" / "worktrees" / "1-finished-item"
    item_on_branch = worktree / "docs/superpowers/backlog/001-finished-item.md"
    item_on_branch.write_text(
        item_on_branch.read_text().replace("status: in-progress", "status: in-review")
    )
    subprocess.run(["git", "add", "-A"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "mark in-review"], cwd=worktree, check=True)

    stage2_repo.write_item(2, "Second Item", priority="medium", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 2")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert "item 1 is 'in-review'" in result.stdout or "awaiting review" in result.stdout
    on_branch_2 = stage2_repo.git(
        "show", "item/2-second-item:docs/superpowers/backlog/002-second-item.md"
    ).stdout
    assert "status: in-progress" in on_branch_2


def test_retitle_during_changes_requested_reuses_existing_branch(stage2_repo):
    stage2_repo.write_item(1, "Old Title", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # claims item 1 -> branch item/1-old-title

    # Simulate finished work on the branch: an extra file marking "real" work,
    # then mark in-review (as a completed Stage 2 run would). Edit inside the
    # branch's own worktree, since the branch is already checked out there.
    worktree = stage2_repo.path / ".claude" / "worktrees" / "1-old-title"
    (worktree / "WORK_DONE.txt").write_text("implementation happened here\n")
    item_on_branch = worktree / "docs/superpowers/backlog/001-old-title.md"
    item_on_branch.write_text(
        item_on_branch.read_text().replace("status: in-progress", "status: in-review")
    )
    subprocess.run(["git", "add", "-A"], cwd=worktree, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "did the actual work + mark in-review"], cwd=worktree, check=True)

    # Human retitles the item and requests changes, both on main.
    item_on_main = stage2_repo.path / "docs/superpowers/backlog/001-old-title.md"
    item_on_main.write_text(
        item_on_main.read_text()
        .replace("title: Old Title", "title: New Title")
        .replace("status: queued", "status: changes-requested")
    )
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "retitle + request changes")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    # No sibling branch was created for the new title.
    assert stage2_repo.git("branch", "--list", "item/1-new-title").stdout.strip() == ""
    # The original branch was reused and still has the prior work on it.
    assert stage2_repo.git(
        "show", "item/1-old-title:WORK_DONE.txt"
    ).stdout == "implementation happened here\n"


def test_worktree_already_checked_out_elsewhere_fails_clearly(stage2_repo):
    stage2_repo.write_item(1, "Old Title", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # creates branch item/1-old-title + its own worktree

    # Simulate: the script's own worktree was removed, and a human checked
    # the same branch out in a second worktree (e.g. to test it manually).
    stage2_repo.git(
        "worktree", "remove", "--force",
        str(stage2_repo.path / ".claude" / "worktrees" / "1-old-title"),
    )
    human_worktree = stage2_repo.path.parent / "human-testing"
    stage2_repo.git("worktree", "add", str(human_worktree), "item/1-old-title")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    # A controlled exit (1) with our own clear message, not git's raw "fatal:"
    # failure bubbling up as exit 128 under set -e.
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    combined = result.stdout + result.stderr
    assert "fatal:" not in combined
    assert "item/1-old-title" in combined
    assert str(human_worktree) in combined
    assert "exiting rather than fighting over it" in combined
    # No stray worktree was created at the conventional path.
    assert not (stage2_repo.path / ".claude" / "worktrees" / "1-old-title").exists()
    # main is untouched.
    assert stage2_repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "item/1-old-title"
