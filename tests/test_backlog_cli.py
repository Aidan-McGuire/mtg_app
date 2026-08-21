import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backlog_cli
from backlog_lib import parse_item, slugify

ITEM_TEMPLATE = """---
id: {id}
title: {title}
priority: {priority}
status: {status}
branch: {branch}
created: 2026-08-20
---

## Problem

Body text.
"""


def make_item(tmp_path, id, title, priority="medium", status="queued", branch=""):
    path = tmp_path / f"{id:03d}-{slugify(title)}.md"
    path.write_text(ITEM_TEMPLATE.format(id=id, title=title, priority=priority, status=status, branch=branch))
    return path


def test_select_prints_chosen_path_and_returns_zero(tmp_path, capsys):
    path = make_item(tmp_path, 1, "Only item", priority="high", status="queued")
    rc = backlog_cli.main(["select", "--dir", str(tmp_path)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == str(path)


def test_select_returns_one_when_nothing_actionable(tmp_path, capsys):
    make_item(tmp_path, 1, "Done", status="accepted")
    rc = backlog_cli.main(["select", "--dir", str(tmp_path)])
    assert rc == 1
    assert capsys.readouterr().out.strip() == ""


def test_claim_sets_in_progress_and_branch(tmp_path, capsys):
    path = make_item(tmp_path, 3, "Deck page tweak", priority="medium", status="queued")
    rc = backlog_cli.main(["claim", str(path)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "item/3-deck-page-tweak"
    item = parse_item(path)
    assert item.status == "in-progress"
    assert item.branch == "item/3-deck-page-tweak"


def test_claim_is_idempotent_on_resume(tmp_path, capsys):
    path = make_item(tmp_path, 3, "Deck page tweak", status="in-progress", branch="item/3-deck-page-tweak")
    rc = backlog_cli.main(["claim", str(path)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "item/3-deck-page-tweak"


def test_branch_name_prints_derived_branch_without_writing(tmp_path, capsys):
    path = make_item(tmp_path, 3, "Deck page tweak", status="queued")
    before = path.read_text()
    rc = backlog_cli.main(["branch-name", str(path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "item/3-deck-page-tweak"
    assert path.read_text() == before
    assert parse_item(path).status == "queued"


def test_branch_name_prefers_already_assigned_branch(tmp_path, capsys):
    path = make_item(tmp_path, 3, "Renamed since claim", branch="item/3-deck-page-tweak")
    rc = backlog_cli.main(["branch-name", str(path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "item/3-deck-page-tweak"


def test_find_by_id_prints_matching_item_path(tmp_path, capsys):
    make_item(tmp_path, 1, "First item")
    target = make_item(tmp_path, 12, "Target item")
    rc = backlog_cli.main(["find-by-id", "12", "--dir", str(tmp_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == str(target)


def test_find_by_id_returns_one_when_missing(tmp_path, capsys):
    make_item(tmp_path, 1, "First item")
    rc = backlog_cli.main(["find-by-id", "99", "--dir", str(tmp_path)])
    assert rc == 1
    assert capsys.readouterr().out.strip() == ""


def test_finish_sets_in_review(tmp_path, capsys):
    path = make_item(tmp_path, 4, "Finished item", status="in-progress", branch="item/4-finished-item")
    rc = backlog_cli.main(["finish", str(path)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "item/4-finished-item"
    item = parse_item(path)
    assert item.status == "in-review"
