import sqlite3
import requests
import gzip
import json
from pathlib import Path
from decimal import Decimal

DB_PATH = Path("mtg.db")
BATCH_SIZE = 1000

# Scryfall requires a descriptive User-Agent and an Accept header;
# the default python-requests User-Agent is rejected with a 400.
HEADERS = {
    "User-Agent": "MTGApp/1.0",
    "Accept": "application/json",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def get_bulk_download_url():
    print("Fetching Scryfall bulk metadata...")
    r = requests.get("https://api.scryfall.com/bulk-data", headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    for item in data["data"]:
        if item["type"] == "default_cards":
            return item["jsonl_download_uri"]

    raise RuntimeError("default_cards bulk data not found.")


def sort_colors(colors):
    if not colors:
        return ""
    return "".join(sorted(colors))


def extract_image_uri(card):
    if "image_uris" in card:
        return card["image_uris"].get("normal")

    if "card_faces" in card:
        for face in card["card_faces"]:
            if "image_uris" in face:
                return face["image_uris"].get("normal")

    return None


def extract_pt(card):
    """Return (power, toughness) from the card or its front face, else (None, None)."""
    if card.get("power") is not None or card.get("toughness") is not None:
        return card.get("power"), card.get("toughness")
    for face in card.get("card_faces", []):
        if face.get("power") is not None or face.get("toughness") is not None:
            return face.get("power"), face.get("toughness")
    return None, None


def normalize_number(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _stream_cards(download_url):
    """Return an iterator of card dicts from the streamed, gzip-decoded Scryfall bulk
    data. The file is JSONL (one complete JSON object per line), not a single
    top-level JSON array."""
    response = requests.get(download_url, stream=True, headers=HEADERS)
    response.raise_for_status()
    gzip_file = gzip.GzipFile(fileobj=response.raw)
    for line in gzip_file:
        line = line.strip()
        if line:
            yield json.loads(line)


def import_cards():
    download_url = get_bulk_download_url()
    print("Downloading and streaming bulk data...")

    conn = get_connection()
    cur = conn.cursor()

    existing = {row[0] for row in cur.execute("SELECT oracle_id FROM cards")}
    seen_oracle_ids = set()
    batch = 0
    processed = 0
    inserted = 0
    updated = 0

    for card in _stream_cards(download_url):
        try:
            if card.get("layout") in ("token", "art_series"):
                continue
            if card.get("digital"):
                continue

            oracle_id = card.get("oracle_id")
            if not oracle_id or oracle_id in seen_oracle_ids:
                continue
            seen_oracle_ids.add(oracle_id)

            power, toughness = extract_pt(card)
            values = (
                card.get("name"),
                card.get("mana_cost"),
                normalize_number(card.get("cmc")),
                card.get("type_line"),
                card.get("oracle_text"),
                sort_colors(card.get("colors")),
                sort_colors(card.get("color_identity")),
                extract_image_uri(card),
                power,
                toughness,
            )

            if oracle_id in existing:
                cur.execute("""
                    UPDATE cards SET
                        name = ?, mana_cost = ?, cmc = ?, type_line = ?,
                        oracle_text = ?, colors = ?, color_identity = ?,
                        image_uri = ?, power = ?, toughness = ?
                    WHERE oracle_id = ?
                """, (*values, oracle_id))
                cur.execute("""
                    UPDATE cards_fts SET name = ?, oracle_text = ?
                    WHERE rowid = (SELECT rowid FROM cards WHERE oracle_id = ?)
                """, (card.get("name"), card.get("oracle_text"), oracle_id))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO cards (
                        name, mana_cost, cmc, type_line, oracle_text,
                        colors, color_identity, image_uri, power, toughness, oracle_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (*values, oracle_id))
                cur.execute(
                    "INSERT INTO cards_fts (name, oracle_text) VALUES (?, ?)",
                    (card.get("name"), card.get("oracle_text")),
                )
                inserted += 1

            batch += 1
            processed += 1
            if batch >= BATCH_SIZE:
                conn.commit()
                print(f"Processed {processed} cards...")
                batch = 0
        except Exception as e:
            print("Skipping card, error:", e)
            continue

    conn.commit()
    print(f"Finished importing cards. {inserted} new, {updated} updated, {processed} processed.")
    conn.close()
    return {"inserted": inserted, "updated": updated, "processed": processed}

if __name__ == "__main__":
    import_cards()
