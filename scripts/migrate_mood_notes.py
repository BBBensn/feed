#!/usr/bin/env python3
"""
One-time migration: Obsidian `type: mood` notes -> journal_entries (Postgres).

Not part of the running app — run manually, once, from a machine with vault read
access and a Postgres connection (e.g. via an SSH tunnel to the server).

Usage:
    python3 migrate_mood_notes.py --vault-path /path/to/01_Journal --dry-run
    python3 migrate_mood_notes.py --vault-path /path/to/01_Journal --database-url postgresql://...

Frontmatter field names in the source notes are capitalized (Valenz, Zusammenhang,
Beschreibung, Tagesreflexion) -- these are lowercased on the way into `fields` JSONB.
"""

import argparse
import re
import sys
from pathlib import Path

import frontmatter
import psycopg2


DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d{4}))?-")


def date_from_filename(stem):
    m = DATE_RE.match(stem)
    if not m:
        return None
    date_part, time_part = m.group(1), m.group(2)
    if time_part:
        return f"{date_part}T{time_part[:2]}:{time_part[2:]}:00"
    return f"{date_part}T12:00:00"


def parse_date(meta_date_created):
    """Mirrors feed-api's parse_date: expects 'YYYY-MM-DD HH:MM:SS' or similar."""
    if not meta_date_created:
        return None
    s = str(meta_date_created).strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", s)
    if m:
        return f"{m.group(1)}T{m.group(2)}:00"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})$", s)
    if m:
        return f"{m.group(1)}T12:00:00"
    return None


def load_mood_notes(vault_path):
    """Find all notes that resolve to type 'mood' -- same fallback logic as
    feed-api's load_note(): explicit frontmatter `type` first, else folder name."""
    notes = []
    for md_file in vault_path.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        try:
            post = frontmatter.load(str(md_file))
        except Exception as e:
            print(f"  SKIP (parse error): {md_file} -- {e}")
            continue
        meta = post.metadata
        note_type = str(meta.get("type", "")).lower() or md_file.parent.name.lower()
        if note_type != "mood":
            continue

        entry_date = parse_date(meta.get("date_created")) or date_from_filename(md_file.stem)
        if not entry_date:
            print(f"  SKIP (no date): {md_file}")
            continue

        valenz = meta.get("Valenz")
        zusammenhang = meta.get("Zusammenhang") or []
        beschreibung = meta.get("Beschreibung") or []
        tagesreflexion = meta.get("Tagesreflexion", False)
        if isinstance(zusammenhang, str):
            zusammenhang = [zusammenhang]
        if isinstance(beschreibung, str):
            beschreibung = [beschreibung]

        notes.append({
            "path": md_file,
            "entry_date": entry_date,
            "body": (post.content or "").strip(),
            "tags": meta.get("tags") or ["mood"],
            "fields": {
                "valenz": int(valenz) if valenz is not None else None,
                "zusammenhang": zusammenhang,
                "beschreibung": beschreibung,
                "tagesreflexion": bool(tagesreflexion) if isinstance(tagesreflexion, bool)
                                  else str(tagesreflexion).lower() == "true",
            },
            "migrated_from": "apple_journal" if meta.get("migrated_from") == "apple_journal" else "obsidian",
        })
    notes.sort(key=lambda n: n["entry_date"])
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-path", required=True, help="Path to the 01_Journal folder")
    ap.add_argument("--database-url", help="Postgres connection string (required unless --dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be inserted, don't write")
    ap.add_argument("--sample", type=int, default=5, help="How many sample rows to print in dry-run")
    args = ap.parse_args()

    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        sys.exit(f"Vault path does not exist: {vault_path}")

    notes = load_mood_notes(vault_path)
    print(f"Found {len(notes)} mood notes to migrate.")

    if args.dry_run:
        print(f"\n--dry-run: showing {min(args.sample, len(notes))} of {len(notes)} (oldest first):\n")
        for n in notes[:args.sample]:
            print(f"  {n['entry_date']}  valenz={n['fields']['valenz']}  "
                  f"zusammenhang={n['fields']['zusammenhang']}  "
                  f"beschreibung={n['fields']['beschreibung']}  "
                  f"tagesreflexion={n['fields']['tagesreflexion']}  "
                  f"migrated_from={n['migrated_from']}  ({n['path'].name})")
        return

    if not args.database_url:
        sys.exit("--database-url is required unless --dry-run")

    conn = psycopg2.connect(args.database_url)
    cur = conn.cursor()
    inserted = 0
    for n in notes:
        cur.execute(
            """INSERT INTO journal_entries
                   (entry_type, entry_date, body, tags, fields, migrated_from, source)
               VALUES ('mood', %s, %s, %s, %s, %s, 'migration')""",
            (n["entry_date"], n["body"], n["tags"],
             __import__("json").dumps(n["fields"]), n["migrated_from"])
        )
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {inserted} mood entries into journal_entries.")


if __name__ == "__main__":
    main()
