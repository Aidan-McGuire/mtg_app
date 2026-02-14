import sqlite3
import requests
import ijson
import gzip
from pathlib import Path
from decimal import Decimal

DB_PATH = Path("mtg.db")
BATCH_SIZE = 1000


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def get_bulk_download_url():
    print("Fetching Scryfall bulk metadata...")
    r = requests.get("https://api.scryfall.com/bulk-data")
    r.raise_for_status()
    data = r.json()

    for item in data["data"]:
        if item["type"] == "default_cards":
            return item["download_uri"]

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

def normalize_number(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def import_cards():
    download_url = get_bulk_download_url()
    print("Downloading and streaming bulk data...")
    
    response = requests.get(download_url, stream=True)
    response.raise_for_status()

    conn = get_connection()
    cur = conn.cursor()

    seen_oracle_ids = set()
    batch = 0
    inserted = 0

    gzip_file = gzip.GzipFile(fileobj=response.raw)
    parser = ijson.items(gzip_file, "item")

    for card in parser:
        try:
          # Skip tokens and digital-only cards
          if card.get("layout") == "token":
              continue
          if card.get("digital"):
              continue

          oracle_id = card.get("oracle_id")
          if not oracle_id:
            continue

          if oracle_id in seen_oracle_ids:
              continue

          seen_oracle_ids.add(oracle_id)

          cur.execute("""
              INSERT OR IGNORE INTO cards (
                  oracle_id,
                  name,
                  mana_cost,
                  cmc,
                  type_line,
                  oracle_text,
                  colors,
                  color_identity,
                  image_uri
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          """, (
              oracle_id,
              card.get("name"),
              card.get("mana_cost"),
              normalize_number(card.get("cmc")),
              card.get("type_line"),
              card.get("oracle_text"),
              sort_colors(card.get("colors")),
              sort_colors(card.get("color_identity")),
              extract_image_uri(card)
          ))

          cur.execute("""
          INSERT INTO cards_fts (name, oracle_text)
          VALUES (?, ?)
          """, (
              card.get("name"),
              card.get("oracle_text")
          ))

          batch += 1
          inserted += 1

          if batch >= BATCH_SIZE:
              conn.commit()
              print(f"Inserted {inserted} cards...")
              batch = 0
        except Exception as e:
          print("Skipping card, error:", e)
          continue

    conn.commit()

    print("Finished inserting cards.")
    conn.close()

if __name__ == "__main__":
    import_cards()
