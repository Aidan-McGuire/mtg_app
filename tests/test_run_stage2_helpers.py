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
