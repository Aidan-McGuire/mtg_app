# Fix Ambiguous Import Match Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `lookup_card_id` in `app.py` never silently pick one of several matching cards for a decklist name — an ambiguous match must resolve exactly like an unmatched name (routed to `not_found` / `import_failures`), not to an arbitrary row.

**Architecture:** `lookup_card_id` has 3 sequential match tiers (exact name, MDFC single-slash-normalized name, front-face-only `LIKE` prefix), each currently doing `... LIMIT 1` and returning the first row found. Change each tier to fetch up to 2 rows and only return a match when exactly 1 row came back; when 2+ rows come back, treat that tier as failed (return `None` for the whole lookup) rather than falling through or guessing. No caller changes are needed — `import_collection` and `import_deck` already route a `None` return into the existing `not_found` / `_record_import_failure` path.

**Tech Stack:** Python, FastAPI, sqlite3, pytest (see `tests/conftest.py` for the `client`/`db_path` fixtures — an in-memory-style temp-file SQLite DB seeded with a small fixed schema per test).

**Spec:** `docs/superpowers/backlog/016-fix-ambiguous-import-match.md`

## Global Constraints

- No caller-facing behavior change for any name that matches exactly one card at whichever tier resolves it — this is a pure precision fix, not a new feature.
- No schema changes. No new columns on `import_failures`.
- Ambiguous matches must be indistinguishable, from the API's perspective, from a genuinely unmatched name — same `not_found` list entry, same `import_failures` row shape.

---

### Task 1: `lookup_card_id` never resolves an ambiguous tier

**Files:**
- Modify: `app.py:257-281` (the `lookup_card_id` function)
- Test: `tests/test_import_failures.py` (append new test functions; follow the existing file's style — raw `sqlite3` inserts against `db_path`, then exercise behavior through the `client` fixture's `/api/collection/import` endpoint)

**Interfaces:**
- Consumes: nothing new — `lookup_card_id(cur, name: str) -> int | None` keeps its exact signature; only its internal query/branch logic changes.
- Produces: nothing new for other tasks — this is the only task in this plan. `import_collection` (`app.py:537`) and `import_deck` (`app.py:649`) already call `lookup_card_id` and already handle a `None` return via `not_found.append(name)` / `_record_import_failure(cur, ...)` (`app.py:284`) — no changes needed there.

- [ ] **Step 1: Write a failing test for an ambiguous exact-name match (tier 1)**

Append to `tests/test_import_failures.py`:

```python
def test_ambiguous_exact_name_match_is_not_found(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('dup-a', 'Duplicate Name Card', NULL, 1, 'Creature')"
    )
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('dup-b', 'Duplicate Name Card', NULL, 1, 'Creature')"
    )
    conn.commit()
    conn.close()

    r = client.post("/api/collection/import", json={"list": "1x Duplicate Name Card"})
    assert r.status_code == 200
    assert r.json()["not_found"] == ["Duplicate Name Card"]

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM import_failures WHERE card_name = 'Duplicate Name Card'"
    ).fetchone()[0]
    conn.close()
    assert count == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_import_failures.py::test_ambiguous_exact_name_match_is_not_found -v`
Expected: FAIL — today's `LIMIT 1` silently resolves to one of the two rows, so `not_found` is `[]` and no `import_failures` row is written. The assertion on `not_found` (or the `count == 1` assertion) fails.

- [ ] **Step 3: Write a failing test for an ambiguous MDFC-normalized match (tier 2)**

Append to `tests/test_import_failures.py`:

```python
def test_ambiguous_mdfc_normalized_match_is_not_found(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('mdfc-a', 'Riverside // Split', NULL, 2, 'Land')"
    )
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('mdfc-b', 'Riverside // Split', NULL, 2, 'Land')"
    )
    conn.commit()
    conn.close()

    # Single-slash form, as Moxfield/Archidekt export MDFCs — normalizes to
    # "Riverside // Split", which now matches both rows above.
    r = client.post("/api/collection/import", json={"list": "1x Riverside / Split"})
    assert r.status_code == 200
    assert r.json()["not_found"] == ["Riverside / Split"]

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM import_failures WHERE card_name = 'Riverside / Split'"
    ).fetchone()[0]
    conn.close()
    assert count == 1
```

- [ ] **Step 4: Run it to verify it fails**

Run: `pytest tests/test_import_failures.py::test_ambiguous_mdfc_normalized_match_is_not_found -v`
Expected: FAIL, same reason as Step 2 but for tier 2.

- [ ] **Step 5: Write a failing test for an ambiguous front-face-only match (tier 3)**

Append to `tests/test_import_failures.py`:

```python
def test_ambiguous_front_face_only_match_is_not_found(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('face-a', 'Shared Front // Back One', NULL, 2, 'Land')"
    )
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('face-b', 'Shared Front // Back Two', NULL, 2, 'Land')"
    )
    conn.commit()
    conn.close()

    # User wrote just the front face — matches both rows' "Shared Front //%" prefix.
    r = client.post("/api/collection/import", json={"list": "1x Shared Front"})
    assert r.status_code == 200
    assert r.json()["not_found"] == ["Shared Front"]

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM import_failures WHERE card_name = 'Shared Front'"
    ).fetchone()[0]
    conn.close()
    assert count == 1
```

- [ ] **Step 6: Run it to verify it fails**

Run: `pytest tests/test_import_failures.py::test_ambiguous_front_face_only_match_is_not_found -v`
Expected: FAIL, same reason as Step 2 but for tier 3.

- [ ] **Step 7: Write regression tests locking in today's single-match behavior for tiers 2 and 3**

These tiers have no existing coverage; add them now so the upcoming implementation change can't accidentally break the happy path it doesn't own a test for yet. Append to `tests/test_import_failures.py`:

```python
def test_unambiguous_mdfc_normalized_match_still_resolves(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('mdfc-solo', 'Lonely // Pathway', NULL, 2, 'Land')"
    )
    conn.commit()
    conn.close()

    r = client.post("/api/collection/import", json={"list": "1x Lonely / Pathway"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []


def test_unambiguous_front_face_only_match_still_resolves(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('face-solo', 'Solo Front // Solo Back', NULL, 2, 'Land')"
    )
    conn.commit()
    conn.close()

    r = client.post("/api/collection/import", json={"list": "1x Solo Front"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []
```

- [ ] **Step 8: Run the two regression tests to verify they pass against today's code**

Run: `pytest tests/test_import_failures.py::test_unambiguous_mdfc_normalized_match_still_resolves tests/test_import_failures.py::test_unambiguous_front_face_only_match_still_resolves -v`
Expected: PASS — these describe existing behavior, confirming the baseline before the implementation change.

- [ ] **Step 9: Implement the fix in `lookup_card_id`**

Replace the function body in `app.py` (currently lines 257-281):

```python
def lookup_card_id(cur, name: str) -> int | None:
    """Look up a card id by name, handling MDFC slash variants and smart quotes.

    Returns None both when no card matches and when a tier's query matches
    more than one card — an ambiguous match is never silently resolved to
    one of several candidates.
    """
    name = name.translate(_SMART_QUOTE_TRANSLATION)

    # 1. Exact match
    cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 2", (name,))
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]["id"]
    if len(rows) > 1:
        return None

    # 2. Single slash → double slash (Moxfield/Archidekt export MDFCs as "A / B")
    normalized = name.replace(' / ', ' // ')
    if normalized != name:
        cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 2", (normalized,))
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["id"]
        if len(rows) > 1:
            return None

    # 3. Front-face-only (user wrote just "Bala Ged Recovery" without the back face)
    cur.execute(
        "SELECT id FROM cards WHERE name LIKE ? COLLATE NOCASE LIMIT 2",
        (name + ' //%',)
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]["id"]
    return None
```

- [ ] **Step 10: Run all 5 new tests to verify they pass**

Run: `pytest tests/test_import_failures.py -v`
Expected: PASS for every test in the file, including the 3 ambiguous-match tests from Steps 1-6 (now passing) and the 2 regression tests from Step 7 (still passing).

- [ ] **Step 11: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS — every existing test (collection/deck import, tags, filters, backlog CLI, etc.) still passes unchanged, since the only behavior change is what happens when a tier matches 2+ rows, which no existing test constructs.

- [ ] **Step 12: Commit**

```bash
git add app.py tests/test_import_failures.py
git commit -m "fix: never silently resolve an ambiguous name match during import"
```
