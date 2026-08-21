"""Parsing and selection logic for docs/superpowers/backlog/*.md items.

See docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PRIORITIES = {"high": 0, "medium": 1, "low": 2}
ACTIONABLE_STATUSES = {"queued", "changes-requested"}

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


@dataclass
class BacklogItem:
    path: Path
    id: int
    title: str
    priority: str
    status: str
    branch: str
    created: str
    body: str

    def select_priority(self) -> int:
        """Ordering key: changes-requested is bumped *above* high — it strictly beats a
        real high-priority item rather than tying with it (stored priority is untouched)."""
        if self.status == "changes-requested":
            return -1
        return PRIORITIES.get(self.priority, PRIORITIES["low"])


def parse_item(path: Path) -> BacklogItem:
    text = path.read_text()
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path} has no valid frontmatter block")
    raw_frontmatter, body = match.groups()
    values = {}
    for line in raw_frontmatter.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
    return BacklogItem(
        path=path,
        id=int(values["id"]),
        title=values.get("title", ""),
        priority=values.get("priority", "low"),
        status=values.get("status", "queued"),
        branch=values.get("branch", ""),
        created=values.get("created", ""),
        body=body,
    )


def write_item(item: BacklogItem) -> None:
    frontmatter_lines = [
        f"id: {item.id:03d}",
        f"title: {item.title}",
        f"priority: {item.priority}",
        f"status: {item.status}",
        f"branch: {item.branch}",
        f"created: {item.created}",
    ]
    text = "---\n" + "\n".join(frontmatter_lines) + "\n---\n" + item.body
    item.path.write_text(text)


def list_items(backlog_dir: Path) -> list[BacklogItem]:
    """Parse every backlog item in backlog_dir.

    A file that looks like an item by name but fails to parse is skipped with a
    warning on stderr rather than raising: one malformed or non-item .md file
    dropped into the backlog directory must not take down the whole workflow.
    """
    item_pattern = re.compile(r"^\d+-.+\.md$")
    items = []
    for p in sorted(Path(backlog_dir).glob("*.md")):
        if not item_pattern.match(p.name):
            continue
        try:
            items.append(parse_item(p))
        except Exception as exc:
            print(f"warning: skipping unparseable backlog file {p.name}: {exc}", file=sys.stderr)
    return items


def select_next(items: list[BacklogItem]) -> BacklogItem | None:
    in_progress = [i for i in items if i.status == "in-progress"]
    if in_progress:
        return sorted(in_progress, key=lambda i: i.id)[0]
    actionable = [i for i in items if i.status in ACTIONABLE_STATUSES]
    if not actionable:
        return None
    return sorted(actionable, key=lambda i: (i.select_priority(), i.id))[0]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return slug.strip("-")


def branch_name(item: BacklogItem) -> str:
    """The canonical branch name for an item: item/<id>-<slug-of-title>."""
    return f"item/{item.id}-{slugify(item.title)}"
