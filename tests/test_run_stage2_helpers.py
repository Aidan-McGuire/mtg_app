import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_stage2.sh"


def _source_and_call(func_call, cwd):
    """Source run_stage2.sh (defines functions only, main() is guarded) then
    run one function call, returning its captured stdout."""
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" && {func_call}'],
        cwd=cwd, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_id_from_branch_strips_prefix_and_slug(tmp_path):
    out = _source_and_call("id_from_branch 'item/16-collection-deck-import'", tmp_path)
    assert out == "16"


def test_id_from_branch_single_digit(tmp_path):
    out = _source_and_call("id_from_branch 'item/1-sample-item'", tmp_path)
    assert out == "1"


def test_status_on_main_reads_status_field(tmp_path):
    item = tmp_path / "item.md"
    item.write_text("---\nid: 001\ntitle: X\npriority: low\nstatus: changes-requested\nbranch: \ncreated: 2026-08-26\n---\n\nBody\n")
    out = _source_and_call(f"status_on_main '{item}'", tmp_path)
    assert out == "changes-requested"


def test_status_on_main_missing_file_prints_nothing(tmp_path):
    out = _source_and_call(f"status_on_main '{tmp_path}/does-not-exist.md'", tmp_path)
    assert out == ""


def _init_scratch_repo(tmp_path):
    repo = (tmp_path / "repo").resolve()
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "item/1-foo"], cwd=repo, check=True)
    return repo


def test_assert_in_worktree_passes_when_toplevel_and_head_match(tmp_path):
    # Sourcing run_stage2.sh runs its own `cd "$REPO_ROOT"` as a side effect
    # (REPO_ROOT resolved from the *script's* real location), so `cd` back to
    # the scratch repo afterwards before calling the function under test.
    repo = _init_scratch_repo(tmp_path)
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" && cd "{repo}" && WORKTREE_DIR="{repo}" BRANCH="item/1-foo" assert_in_worktree'],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_assert_in_worktree_fails_when_head_does_not_match_expected_branch(tmp_path):
    repo = _init_scratch_repo(tmp_path)
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" && cd "{repo}" && WORKTREE_DIR="{repo}" BRANCH="item/1-different" assert_in_worktree'],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "item/1-different" in result.stderr
