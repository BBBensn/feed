#!/usr/bin/env python3
"""
One-time migration: remaining Obsidian journal types -> journal_entries (Postgres).

Covers diary, reflexion, symptome, therapie, fits, arbeit, ideas, project_log.
`mood` is handled by migrate_mood_notes.py (already run separately) and is skipped
here by default -- pass --include-mood to also re-scan mood notes (e.g. for a fresh
re-migration), but note this will create DUPLICATES if mood was already migrated.

Not part of the running app -- run manually, once, from a machine with vault read
access and a Postgres connection (e.g. via an SSH tunnel to the server).

Usage:
    python3 migrate_journal_notes.py --vault-path /path/to/01_Journal --dry-run
    python3 migrate_journal_notes.py --vault-path /path/to/01_Journal --database-url postgresql://...
"""

import argparse
import json
import re
import sys
from pathlib import Path

import frontmatter
import psycopg2


# Folder name (lowercased) -> canonical entry_type, used as a fallback when a note
# has no explicit `type:` frontmatter field (rare, but happens on a few old notes).
FOLDER_TYPE_MAP = {
    "diary": "diary", "fits": "fits", "reflexionen": "reflexion",
    "symptome": "symptome", "therapie": "therapie", "arbeit": "arbeit",
    "ideas": "ideas", "projects": "project_log",
}
# Frontmatter `type:` value -> canonical entry_type (several notes use the singular
# form -- fit/idea/symptom -- while the schema's CHECK constraint uses the plural).
TYPE_ALIASES = {
    "fit": "fits", "idea": "ideas", "symptom": "symptome", "reflexionen": "reflexion",
}
VALID_TYPES = {"diary", "reflexion", "symptome", "therapie", "fits", "arbeit", "ideas", "project_log", "mood"}

DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-?")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d{4}))?-")


def canonical_type(raw_type, folder_name):
    t = (str(raw_type or "")).lower().strip()
    t = TYPE_ALIASES.get(t, t)
    if t in VALID_TYPES:
        return t
    return FOLDER_TYPE_MAP.get(folder_name.lower())


def date_from_filename(stem):
    m = DATE_RE.match(stem)
    if not m:
        return None
    date_part, time_part = m.group(1), m.group(2)
    if time_part:
        return f"{date_part}T{time_part[:2]}:{time_part[2:]}:00"
    return f"{date_part}T12:00:00"


def parse_date(meta_date_created):
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


def title_from_stem(stem):
    t = DATE_PREFIX_RE.sub("", stem).replace("-", " ").strip()
    return t or None


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def as_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def as_str_or_none(v):
    s = str(v).strip() if v is not None else ""
    return s or None


def extract_fields(entry_type, meta):
    if entry_type == "diary":
        return {"tagesreflexion": as_bool(meta.get("tagesreflexion", False))}
    if entry_type == "reflexion":
        mood = meta.get("mood")
        return {"mood": int(mood) if str(mood).strip().isdigit() else None}
    if entry_type == "symptome":
        return {"kategorie": as_list(meta.get("kategorie"))}
    if entry_type == "therapie":
        return {"session_nr": as_str_or_none(meta.get("session_nr")),
                "therapeut": as_str_or_none(meta.get("therapeut"))}
    if entry_type == "fits":
        return {"location": as_str_or_none(meta.get("location")),
                "anlass": as_str_or_none(meta.get("anlass"))}
    if entry_type == "ideas":
        return {"status": as_str_or_none(meta.get("status")),
                "bereich": as_str_or_none(meta.get("bereich"))}
    if entry_type == "project_log":
        return {"project": as_str_or_none(meta.get("project"))}
    return {}  # arbeit has no structured fields


def load_journal_notes(vault_path, include_mood=False):
    notes = []
    skipped = []
    for md_file in vault_path.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        try:
            post = frontmatter.load(str(md_file))
        except Exception as e:
            skipped.append((md_file, f"parse error: {e}"))
            continue
        meta = post.metadata
        folder = md_file.parent.name
        entry_type = canonical_type(meta.get("type"), folder)
        if entry_type is None:
            skipped.append((md_file, f"unrecognized type/folder ({meta.get('type')!r}/{folder!r})"))
            continue
        if entry_type == "mood" and not include_mood:
            continue

        entry_date = parse_date(meta.get("date_created")) or date_from_filename(md_file.stem)
        if not entry_date:
            skipped.append((md_file, "no usable date"))
            continue

        content = (post.content or "").strip()
        images = IMAGE_RE.findall(content)
        tags = meta.get("tags")
        if isinstance(tags, str):
            tags = [tags]
        tags = tags or [entry_type]

        notes.append({
            "path": md_file,
            "entry_type": entry_type,
            "entry_date": entry_date,
            "title": title_from_stem(md_file.stem),
            "body": content,
            "tags": tags,
            "images": images,
            "fields": extract_fields(entry_type, meta),
            "migrated_from": "obsidian",
        })
    notes.sort(key=lambda n: n["entry_date"])
    return notes, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-path", required=True)
    ap.add_argument("--database-url")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-mood", action="store_true",
                     help="Also migrate mood notes (WARNING: creates duplicates if already migrated)")
    ap.add_argument("--type", help="Only migrate this entry_type (for spot-checking)")
    args = ap.parse_args()

    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        sys.exit(f"Vault path does not exist: {vault_path}")

    notes, skipped = load_journal_notes(vault_path, include_mood=args.include_mood)
    if args.type:
        notes = [n for n in notes if n["entry_type"] == args.type]

    by_type = {}
    for n in notes:
        by_type.setdefault(n["entry_type"], 0)
        by_type[n["entry_type"]] += 1

    print(f"Found {len(notes)} notes to migrate, by type:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")
    if skipped:
        print(f"\nSkipped {len(skipped)} files:")
        for path, reason in skipped:
            print(f"  {path.name}: {reason}")

    if args.dry_run:
        print(f"\n--dry-run: showing up to 3 samples per type\n")
        shown = {}
        for n in notes:
            shown.setdefault(n["entry_type"], 0)
            if shown[n["entry_type"]] >= 3:
                continue
            shown[n["entry_type"]] += 1
            print(f"  [{n['entry_type']}] {n['entry_date']}  title={n['title']!r}  "
                  f"fields={n['fields']}  images={len(n['images'])}  ({n['path'].name})")
        return

    if not args.database_url:
        sys.exit("--database-url is required unless --dry-run")

    conn = psycopg2.connect(args.database_url)
    cur = conn.cursor()
    inserted = 0
    for n in notes:
        cur.execute(
            """INSERT INTO journal_entries
                   (entry_type, entry_date, title, body, tags, images, fields, migrated_from, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'migration')""",
            (n["entry_type"], n["entry_date"], n["title"], n["body"], n["tags"],
             n["images"], json.dumps(n["fields"]), n["migrated_from"])
        )
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"\nInserted {inserted} journal entries.")


if __name__ == "__main__":
    main()
