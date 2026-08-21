#!/usr/bin/env python3
"""CLI for the Stage 2 autonomous backlog workflow.

See docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md.

Subcommands:
    select [--dir DIR]   Print the path of the next item to work (in-progress
                         first, else highest priority among queued/
                         changes-requested). Exit 1 with no output if none.
    claim ITEM_PATH      Mark an item in-progress, assigning a branch name if
                         it doesn't have one yet. Print the branch name.
    finish ITEM_PATH     Mark an item in-review. Print the branch name.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_lib import list_items, parse_item, select_next, slugify, write_item

DEFAULT_BACKLOG_DIR = Path(__file__).resolve().parent.parent / "docs" / "superpowers" / "backlog"


def cmd_select(args):
    items = list_items(Path(args.dir))
    chosen = select_next(items)
    if chosen is None:
        return 1
    print(chosen.path)
    return 0


def cmd_claim(args):
    item = parse_item(Path(args.item_path))
    item.status = "in-progress"
    if not item.branch:
        item.branch = f"item/{item.id}-{slugify(item.title)}"
    write_item(item)
    print(item.branch)
    return 0


def cmd_finish(args):
    item = parse_item(Path(args.item_path))
    item.status = "in-review"
    write_item(item)
    print(item.branch)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    select_parser = sub.add_parser("select")
    select_parser.add_argument("--dir", default=str(DEFAULT_BACKLOG_DIR))

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("item_path")

    finish_parser = sub.add_parser("finish")
    finish_parser.add_argument("item_path")

    args = parser.parse_args(argv)
    handlers = {"select": cmd_select, "claim": cmd_claim, "finish": cmd_finish}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
