# Async Backlog Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the tooling for the three-stage async backlog workflow described in `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md` — a `docs/superpowers/backlog/` item format, a select/claim/finish CLI, a scoped unattended-permission profile, the Stage 2 worker script, and a daily local `launchd` job that fires it.

**Architecture:** Backlog items are markdown files with YAML-ish frontmatter (`id`, `title`, `priority`, `status`, `branch`, `created`) scanned by a small dependency-free Python library (`scripts/backlog_lib.py`) and exposed via a thin CLI (`scripts/backlog_cli.py`) with `select`/`claim`/`finish` subcommands. A shell wrapper (`scripts/run_stage2.sh`) uses that CLI to pick the next item, claims it, sets up (or resumes) an isolated git worktree on `item/<id>-<slug>`, and invokes `claude -p` there with a fixed prompt and a scoped permissions file so the run never blocks waiting for approval it can't get. `launchd` fires the wrapper once daily at 12:00 local time.

**Tech Stack:** Python 3 (stdlib only — no new dependencies), bash, pytest, macOS `launchd`.

## Global Constraints

- No new Python dependencies (repo has no `requirements.txt`/PyYAML today — frontmatter parsing must be hand-rolled, stdlib only).
- Backlog item frontmatter fields, exactly as in the spec: `id`, `title`, `priority` (`high`|`medium`|`low`), `status` (`queued`|`in-progress`|`changes-requested`|`in-review`|`accepted`), `branch`, `created`.
- Selection rule, exactly as in the spec: any `status: in-progress` item wins outright (resume); otherwise pick the highest-priority item among `status: queued` and `status: changes-requested`, with `changes-requested` always treated as `high` priority for ordering purposes only (its stored `priority` field is left untouched); tiebreak by lowest `id`.
- Stage 2 worker: one item per invocation, then stop.
- Stage 2 execution is local only (no cloud sandbox) — daily `launchd` job at 12:00 local time, plus an on-demand path (just running `scripts/run_stage2.sh` directly).
- Unattended runs must use a scoped permission allowlist (not `--dangerously-skip-permissions`), so an action outside the allowlist is denied rather than prompting a human who isn't there.

---

### Task 1: Backlog directory scaffold and docs

**Files:**
- Create: `docs/superpowers/backlog/README.md`
- Create: `docs/superpowers/backlog/TEMPLATE.md`
- Modify: `CLAUDE.md` (append a pointer section)

**Interfaces:**
- Produces: the `docs/superpowers/backlog/` directory that Task 2's `list_items()`/`select_next()` scan, and the frontmatter schema every later task assumes.

- [ ] **Step 1: Create the backlog README**

```markdown
# Backlog

Refined, implementation-ready work items for the async backlog workflow.
Full protocol: `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`.

Each item is one `NNN-slug.md` file (NNN = zero-padded id). Frontmatter:

- `id` — unique integer, matches the NNN filename prefix
- `title` — short name
- `priority` — `high` | `medium` | `low`
- `status` — `queued` | `in-progress` | `changes-requested` | `in-review` | `accepted`
- `branch` — set automatically once claimed (`item/<id>-<slug>`); leave empty when creating an item
- `created` — ISO date

Body: problem statement, approach, acceptance criteria — refined until a
fresh session with zero context could implement it without asking anyone
anything. Copy `TEMPLATE.md` to start a new item, using the next unused id.
```

Save this as `docs/superpowers/backlog/README.md`.

- [ ] **Step 2: Create the item template**

```markdown
---
id: 0
title:
priority: medium
status: queued
branch:
created:
---

## Problem

## Approach

## Acceptance criteria

- [ ]
```

Save this as `docs/superpowers/backlog/TEMPLATE.md`.

- [ ] **Step 3: Add a pointer section to CLAUDE.md**

Append this section to the end of `CLAUDE.md`:

```markdown

## Async Backlog Workflow

Refined, ready-to-implement work lives in `docs/superpowers/backlog/` and is
picked up autonomously by a daily local `launchd` job running
`scripts/run_stage2.sh`. Full protocol:
`docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`.
```

- [ ] **Step 4: Verify and commit**

Run: `ls docs/superpowers/backlog/` — expect `README.md` and `TEMPLATE.md`.

```bash
git add docs/superpowers/backlog/README.md docs/superpowers/backlog/TEMPLATE.md CLAUDE.md
git commit -m "docs: scaffold backlog directory and link it from CLAUDE.md"
```

---

### Task 2: Backlog parsing/selection library

**Files:**
- Create: `scripts/backlog_lib.py`
- Test: `tests/test_backlog_lib.py`

**Interfaces:**
- Produces: `BacklogItem` dataclass with fields `path, id, title, priority, status, branch, created, body` and method `select_priority() -> int`; functions `parse_item(path: Path) -> BacklogItem`, `write_item(item: BacklogItem) -> None`, `list_items(backlog_dir: Path) -> list[BacklogItem]`, `select_next(items: list[BacklogItem]) -> BacklogItem | None`, `slugify(text: str) -> str`. Task 3's CLI consumes all of these by name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_backlog_lib.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backlog_lib import parse_item, write_item, list_items, select_next, slugify


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


def test_slugify():
    assert slugify("Commander gets own section!") == "commander-gets-own-section"
    assert slugify("  Trim -- me  ") == "trim-me"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backlog_lib.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backlog_lib'`

- [ ] **Step 3: Write the implementation**

Create `scripts/backlog_lib.py`:

```python
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
            return PRIORITIES["high"]
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
    return [
        parse_item(p)
        for p in sorted(Path(backlog_dir).glob("*.md"))
        if p.name != "TEMPLATE.md"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backlog_lib.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/backlog_lib.py tests/test_backlog_lib.py
git commit -m "feat: add backlog item parsing and selection library"
```

---

### Task 3: Backlog CLI (select / claim / finish)

**Files:**
- Create: `scripts/backlog_cli.py`
- Test: `tests/test_backlog_cli.py`

**Interfaces:**
- Consumes: `backlog_lib.{parse_item, write_item, list_items, select_next, slugify}` (Task 2).
- Produces: `main(argv: list[str] | None) -> int`, invocable as `python3 scripts/backlog_cli.py select [--dir DIR]` (prints the chosen item's path and exits 0, or exits 1 with no output if nothing actionable), `... claim ITEM_PATH` (prints the branch name, sets `status: in-progress`), `... finish ITEM_PATH` (prints the branch name, sets `status: in-review`). Task 5's `scripts/run_stage2.sh` consumes this CLI's stdout/exit codes directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_backlog_cli.py`:

```python
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


def test_finish_sets_in_review(tmp_path, capsys):
    path = make_item(tmp_path, 4, "Finished item", status="in-progress", branch="item/4-finished-item")
    rc = backlog_cli.main(["finish", str(path)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == "item/4-finished-item"
    item = parse_item(path)
    assert item.status == "in-review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backlog_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backlog_cli'`

- [ ] **Step 3: Write the implementation**

Create `scripts/backlog_cli.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backlog_cli.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/backlog_cli.py
git add scripts/backlog_cli.py tests/test_backlog_cli.py
git commit -m "feat: add backlog select/claim/finish CLI"
```

---

### Task 4: Scoped unattended-permission profile and Stage 2 prompt

**Files:**
- Create: `.claude/stage2.settings.json`
- Create: `scripts/stage2_prompt.txt`

**Interfaces:**
- Produces: a settings file passed to `claude -p --settings .claude/stage2.settings.json` by Task 5, and a prompt template with an `{ITEM_PATH}` placeholder substituted by Task 5's wrapper script.

- [ ] **Step 1: Write the scoped permissions file**

Create `.claude/stage2.settings.json`. This is deliberately much narrower than the interactive `.claude/settings.local.json` — it must not allow pushing/resetting `main`, force-pushing, or destroying worktrees, since nobody is watching this run:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 scripts/backlog_cli.py *)",
      "Bash(python3 -m pytest *)",
      "Bash(pytest *)",
      "Bash(python3 *)",
      "Bash(python main.py)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git log *)",
      "Bash(git branch --show-current)",
      "Bash(git push origin item/*)",
      "Bash(uvicorn app:app *)",
      "Bash(pkill -f \"uvicorn app:app*\")",
      "Bash(curl -s http://127.0.0.1:*)"
    ],
    "deny": [
      "Bash(git push origin main*)",
      "Bash(git push --force*)",
      "Bash(git push -f*)",
      "Bash(git reset --hard*)",
      "Bash(git checkout main*)",
      "Bash(git merge*)",
      "Bash(git worktree remove*)",
      "Bash(rm -rf*)"
    ]
  }
}
```

- [ ] **Step 2: Write the Stage 2 prompt template**

Create `scripts/stage2_prompt.txt`:

```
You are running as the unattended Stage 2 worker for this repo's async
backlog workflow. Follow the protocol in
docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md exactly.
No human is present to answer questions, approve choices, or unblock you —
make the most reasonable judgment call yourself and keep going rather than
stopping to ask.

You are already inside the correct git worktree, on the correct branch, and
the backlog item at {ITEM_PATH} has already been claimed (status:
in-progress) for you.

Do this:
1. Read {ITEM_PATH} for the problem statement, approach, and acceptance
   criteria (and any "## Review feedback" section, if present).
2. If docs/superpowers/plans/ has no plan file for this item yet, use the
   writing-plans skill to write one from the item's spec.
3. Implement the plan using the executing-plans skill, working straight
   through checkpoints without pausing for review (there is no one to
   review) unless you hit a genuine blocker.
4. Commit after each meaningful step, so progress is never lost even if
   this run is cut off partway through.
5. When the plan is fully done and tests pass: run
   `python3 scripts/backlog_cli.py finish {ITEM_PATH}`, push the current
   branch to origin, and send a push notification saying which item is
   ready for review.
6. If you cannot finish (blocked, ambiguous spec, failing tests you can't
   resolve): stop after committing whatever progress you have. Do not run
   `finish` and do not push. Leave the item's status as in-progress —
   tomorrow's run will resume from here by re-reading this same prompt
   against the current state of this branch.
```

- [ ] **Step 3: Verify and commit**

Run: `python3 -c "import json; json.load(open('.claude/stage2.settings.json'))"` — expect no output (valid JSON, no exception).

```bash
git add .claude/stage2.settings.json scripts/stage2_prompt.txt
git commit -m "feat: add scoped permission profile and prompt for unattended Stage 2 runs"
```

---

### Task 5: Stage 2 wrapper script

**Files:**
- Create: `scripts/run_stage2.sh`

**Interfaces:**
- Consumes: `scripts/backlog_cli.py {select, claim, finish}` (Task 3), `.claude/stage2.settings.json` and `scripts/stage2_prompt.txt` (Task 4).
- Produces: an executable entry point invoked directly for on-demand runs, and by `launchd` in Task 6.

- [ ] **Step 1: Write the wrapper script**

Create `scripts/run_stage2.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! ITEM_PATH="$(python3 scripts/backlog_cli.py select)"; then
  echo "$(date): no backlog item ready, exiting"
  exit 0
fi

BRANCH="$(python3 scripts/backlog_cli.py claim "$ITEM_PATH")"
WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

if [ ! -d "$WORKTREE_DIR" ]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add "$WORKTREE_DIR" "$BRANCH"
  else
    git worktree add "$WORKTREE_DIR" -b "$BRANCH"
  fi
fi

PROMPT="$(sed "s#{ITEM_PATH}#$ITEM_PATH#g" "$REPO_ROOT/scripts/stage2_prompt.txt")"

cd "$WORKTREE_DIR"
claude -p "$PROMPT" \
  --permission-mode default \
  --settings "$REPO_ROOT/.claude/stage2.settings.json" \
  --output-format text
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/run_stage2.sh
```

- [ ] **Step 3: Smoke test the empty-backlog path**

The real backlog directory is empty at this point in the rollout (per the design decision to seed it separately, later, as ordinary Stage 1 work), so this exercises the "nothing to do" path end-to-end without touching git or spawning `claude`.

Run: `./scripts/run_stage2.sh`
Expected output: `<today's date>: no backlog item ready, exiting`, exit code 0, no new git worktree created (`git worktree list` unchanged).

- [ ] **Step 4: Commit**

```bash
git add scripts/run_stage2.sh
git commit -m "feat: add Stage 2 wrapper script (select, claim, worktree, invoke claude)"
```

---

### Task 6: Daily launchd schedule

**Files:**
- Create: `scripts/com.mcg.mtg-app.stage2.plist`
- Create: `scripts/install_stage2_schedule.sh`

**Interfaces:**
- Consumes: `scripts/run_stage2.sh` (Task 5), invoked with an absolute path.
- Produces: an installed `launchd` agent firing daily at 12:00 local time.

- [ ] **Step 1: Write the launchd plist**

Create `scripts/com.mcg.mtg-app.stage2.plist` (adjust `/Users/mcg/projects/mtg_app` if the repo ever moves):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mcg.mtg-app.stage2</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/mcg/projects/mtg_app/scripts/run_stage2.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>12</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/mcg/projects/mtg_app/.claude/stage2.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/mcg/projects/mtg_app/.claude/stage2.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

- [ ] **Step 2: Write the install script**

Create `scripts/install_stage2_schedule.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DEST="$HOME/Library/LaunchAgents/com.mcg.mtg-app.stage2.plist"

cp "$REPO_ROOT/scripts/com.mcg.mtg-app.stage2.plist" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "Installed. Status:"
launchctl list | grep com.mcg.mtg-app.stage2 || echo "(not showing yet — check again in a moment)"
```

- [ ] **Step 3: Make it executable and run it**

```bash
chmod +x scripts/install_stage2_schedule.sh
./scripts/install_stage2_schedule.sh
```

Expected: the final `launchctl list` line shows `com.mcg.mtg-app.stage2` (a `0` in the first column means it isn't currently running, which is correct outside its scheduled window; a PID means it's mid-run).

- [ ] **Step 4: Commit**

```bash
git add scripts/com.mcg.mtg-app.stage2.plist scripts/install_stage2_schedule.sh
git commit -m "feat: install a daily launchd job that fires the Stage 2 worker at noon"
```

---

## Post-plan note

This plan only stands up the tooling. `docs/superpowers/backlog/` is intentionally left empty afterward — populating it with real refined items is ordinary Stage 1 work, done one item at a time in a normal brainstorming session, per the design spec.

**Two things this plan cannot verify without a real item to run against, and that the first real Stage 2 firing should be watched closely for:**

- `--settings` loads the scoped file *in addition to* whatever settings Claude Code discovers normally, rather than replacing them — it does not fully sandbox the run by itself. In practice this should be fine: `.claude/settings.local.json` (the broad, accumulated interactive allowlist) is untracked, so it won't exist inside a fresh `git worktree` checkout at all. But this hasn't been exercised end-to-end, since Task 5's smoke test only covers the empty-backlog path (no `claude` invocation). Watch the log at `.claude/stage2.log` after the first real run.
- `.claude/settings.json` (tracked, so it *does* exist in the worktree) has a `PostToolUse` hook that restarts `uvicorn` rooted at the main repo path (`/Users/mcg/projects/mtg_app`) on every Edit/Write. It'll keep firing during Stage 2 runs — harmless (just restarts your local dev server), but worth knowing if you see it bounce while a background run is in progress.
