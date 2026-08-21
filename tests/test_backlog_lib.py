import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backlog_lib import (
    branch_name,
    list_items,
    parse_item,
    select_next,
    slugify,
    write_item,
)


ITEM_TEMPLATE = """---
id: {id}
title: {title}
priority: {priority}
status: {status}
branch: {branch}
created: 2026-08-20
---

## Problem

Body text for {title}.
"""


def make_item(tmp_path, id, title, priority="medium", status="queued", branch=""):
    path = tmp_path / f"{id:03d}-{slugify(title)}.md"
    path.write_text(ITEM_TEMPLATE.format(id=id, title=title, priority=priority, status=status, branch=branch))
    return path


def test_parse_item_reads_all_fields(tmp_path):
    path = make_item(tmp_path, 7, "Commander gets own section", priority="medium", status="queued")
    item = parse_item(path)
    assert item.id == 7
    assert item.title == "Commander gets own section"
    assert item.priority == "medium"
    assert item.status == "queued"
    assert item.branch == ""
    assert item.created == "2026-08-20"
    assert "Body text for Commander gets own section." in item.body


def test_write_item_round_trips(tmp_path):
    path = make_item(tmp_path, 1, "Round trip test")
    item = parse_item(path)
    item.status = "in-progress"
    item.branch = "item/1-round-trip-test"
    write_item(item)
    reloaded = parse_item(path)
    assert reloaded.status == "in-progress"
    assert reloaded.branch == "item/1-round-trip-test"
    assert "Body text for Round trip test." in reloaded.body


def test_list_items_ignores_template(tmp_path):
    make_item(tmp_path, 1, "Real item")
    (tmp_path / "TEMPLATE.md").write_text("---\nid: 0\ntitle:\npriority: medium\nstatus: queued\nbranch:\ncreated:\n---\n")
    items = list_items(tmp_path)
    assert len(items) == 1
    assert items[0].title == "Real item"


def test_select_next_prefers_in_progress_over_higher_priority_queued(tmp_path):
    make_item(tmp_path, 1, "High priority queued", priority="high", status="queued")
    make_item(tmp_path, 2, "Low priority in progress", priority="low", status="in-progress")
    chosen = select_next(list_items(tmp_path))
    assert chosen.id == 2


def test_select_next_picks_highest_priority_queued(tmp_path):
    make_item(tmp_path, 1, "Low", priority="low", status="queued")
    make_item(tmp_path, 2, "High", priority="high", status="queued")
    make_item(tmp_path, 3, "Medium", priority="medium", status="queued")
    chosen = select_next(list_items(tmp_path))
    assert chosen.id == 2


def test_select_next_treats_changes_requested_as_high_priority(tmp_path):
    make_item(tmp_path, 1, "High queued", priority="high", status="queued")
    make_item(tmp_path, 2, "Low changes requested", priority="low", status="changes-requested")
    chosen = select_next(list_items(tmp_path))
    assert chosen.id == 2
    assert chosen.priority == "low"


def test_select_next_tiebreaks_by_lowest_id(tmp_path):
    make_item(tmp_path, 5, "First", priority="high", status="queued")
    make_item(tmp_path, 2, "Second", priority="high", status="queued")
    chosen = select_next(list_items(tmp_path))
    assert chosen.id == 2


def test_select_next_returns_none_when_nothing_actionable(tmp_path):
    make_item(tmp_path, 1, "Done", priority="high", status="accepted")
    make_item(tmp_path, 2, "In review", priority="high", status="in-review")
    assert select_next(list_items(tmp_path)) is None


def test_list_items_ignores_non_item_markdown_files(tmp_path):
    make_item(tmp_path, 1, "Real item")
    (tmp_path / "README.md").write_text("# Documentation")
    (tmp_path / "TEMPLATE.md").write_text("---\nid: 0\ntitle:\npriority: medium\nstatus: queued\nbranch:\ncreated:\n---\n")
    items = list_items(tmp_path)
    assert len(items) == 1
    assert items[0].title == "Real item"


def test_list_items_skips_malformed_item_file_with_warning(tmp_path, capsys):
    make_item(tmp_path, 1, "Real item")
    # Matches the item filename pattern (as this repo's dated doc names do) but
    # has no parseable frontmatter — must not take the whole listing down.
    (tmp_path / "2026-08-20-scratch-notes.md").write_text("just some notes, no frontmatter\n")
    items = list_items(tmp_path)
    assert [i.title for i in items] == ["Real item"]
    assert "2026-08-20-scratch-notes.md" in capsys.readouterr().err


def test_write_item_zero_pads_id_on_disk(tmp_path):
    path = make_item(tmp_path, 7, "Padding test")
    item = parse_item(path)
    write_item(item)
    assert "id: 007" in path.read_text()
    assert parse_item(path).id == 7


def test_write_item_does_not_truncate_larger_ids(tmp_path):
    path = make_item(tmp_path, 1234, "Big id")
    item = parse_item(path)
    write_item(item)
    assert "id: 1234" in path.read_text()


def test_branch_name_derives_from_id_and_title(tmp_path):
    item = parse_item(make_item(tmp_path, 3, "Deck page tweak"))
    assert branch_name(item) == "item/3-deck-page-tweak"


def test_slugify():
    assert slugify("Commander gets own section!") == "commander-gets-own-section"
    assert slugify("  Trim -- me  ") == "trim-me"
