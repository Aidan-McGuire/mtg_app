"""Parsing and selection logic for docs/superpowers/backlog/*.md items.

See docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md.
"""
from __future__ import annotations

import re
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
        """Ordering key: changes-requested is always bumped to high (stored priority is untouched)."""
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
        f"id: {item.id}",
        f"title: {item.title}",
        f"priority: {item.priority}",
        f"status: {item.status}",
        f"branch: {item.branch}",
        f"created: {item.created}",
    ]
    text = "---\n" + "\n".join(frontmatter_lines) + "\n---\n" + item.body
    item.path.write_text(text)


def list_items(backlog_dir: Path) -> list[BacklogItem]:
    item_pattern = re.compile(r"^\d+-.+\.md$")
    return [
        parse_item(p)
        for p in sorted(Path(backlog_dir).glob("*.md"))
        if item_pattern.match(p.name)
    ]


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
