#!/usr/bin/env python3
"""Bensn-Feed API — liest Obsidian .md Notes aus 01_Journal und gibt sie als JSON zurück."""

import os
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
import frontmatter

app = Flask(__name__)

VAULT_PATH = Path("/var/www/feed/vault/01_Journal")

# Note-Types die im Feed erscheinen sollen
FEED_TYPES = {
    "diary", "mood", "fits", "reflexionen", "reflexion",
    "symptome", "symptom", "therapie", "arbeit", "projectlog",
    "project", "idea", "ideas"
}

def parse_date(val):
    """Parst verschiedene date_created Formate zu datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def date_from_filename(name):
    """Fallback: Datum aus Dateiname lesen (YYYY-MM-DD-HHmm oder YYYY-MM-DD)."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(\d{4})", name)
    if m:
        try:
            return datetime.strptime(m.group(1) + " " + m.group(2)[:2] + ":" + m.group(2)[2:], "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None

def extract_images(content):
    """Findet iCloud- und normale Bild-Links im Markdown."""
    images = []
    # Markdown Bilder: ![alt](url)
    for m in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", content):
        images.append({"alt": m.group(1), "url": m.group(2)})
    return images

def extract_media_links(content):
    """Findet Spotify/YouTube-Links für oEmbed (später)."""
    links = []
    patterns = [
        ("spotify", r"https://open\.spotify\.com/\S+"),
        ("youtube", r"https://(?:www\.)?youtube\.com/watch\S+"),
        ("youtube", r"https://youtu\.be/\S+"),
    ]
    for platform, pat in patterns:
        for m in re.finditer(pat, content):
            links.append({"platform": platform, "url": m.group(0)})
    return links

def clean_content(content):
    """Entfernt .gitkeep und sehr kurze inhaltslose Bodies."""
    if not content:
        return ""
    return content.strip()

def load_note(path: Path, folder: str):
    """Lädt eine einzelne .md Datei und gibt ein Note-Dict zurück."""
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None

    meta = post.metadata
    content = clean_content(post.content)

    # Typ bestimmen
    note_type = str(meta.get("type", "")).lower() or folder.lower()

    # Datum bestimmen
    dt = parse_date(meta.get("date_created")) or date_from_filename(path.stem)
    if not dt:
        return None  # Ohne Datum nicht im Feed

    # Titel aus Dateiname ableiten (optional)
    stem = path.stem
    # Entferne Datum-Prefix aus Dateiname für lesbaren Titel
    title = re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-?", "", stem).replace("-", " ").strip()

    return {
        "id": path.stem,
        "type": note_type,
        "folder": folder,
        "title": title or None,
        "date": dt.isoformat(),
        "date_modified": str(meta.get("date_modified", "")),
        "tags": meta.get("tags", []),
        "content": content,
        "images": extract_images(content),
        "media_links": extract_media_links(content),
        "meta": {k: str(v) for k, v in meta.items() if k not in ("date_created", "date_modified", "tags", "type")},
        "path": str(path.relative_to(VAULT_PATH.parent.parent)),
    }

def load_all_notes():
    """Liest alle .md Notes aus 01_Journal rekursiv."""
    notes = []
    if not VAULT_PATH.exists():
        return notes

    for md_file in VAULT_PATH.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        folder = md_file.parent.name
        note = load_note(md_file, folder)
        if note:
            notes.append(note)

    # Sortiert nach Datum, neueste zuerst
    notes.sort(key=lambda n: n["date"], reverse=True)
    return notes

@app.route("/api/feed")
def feed():
    """GET /api/feed — alle Notes, optional gefiltert."""
    notes = load_all_notes()

    # Filter: ?type=diary
    type_filter = request.args.get("type", "").lower()
    if type_filter:
        notes = [n for n in notes if n["type"] == type_filter]

    # Filter: ?folder=Diary
    folder_filter = request.args.get("folder", "").lower()
    if folder_filter:
        notes = [n for n in notes if n["folder"].lower() == folder_filter]

    # Limit: ?limit=50
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    notes = notes[:limit]

    return jsonify({
        "count": len(notes),
        "notes": notes
    })

@app.route("/api/feed/<note_id>")
def single_note(note_id):
    """GET /api/feed/<note_id> — einzelne Note."""
    for md_file in VAULT_PATH.rglob("*.md"):
        if md_file.stem == note_id:
            folder = md_file.parent.name
            note = load_note(md_file, folder)
            if note:
                return jsonify(note)
    return jsonify({"error": "Note not found"}), 404

@app.route("/api/feed/stats")
def stats():
    """GET /api/feed/stats — Übersicht."""
    notes = load_all_notes()
    by_type = {}
    by_folder = {}
    for n in notes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
        by_folder[n["folder"]] = by_folder.get(n["folder"], 0) + 1
    return jsonify({
        "total": len(notes),
        "by_type": by_type,
        "by_folder": by_folder,
        "oldest": notes[-1]["date"] if notes else None,
        "newest": notes[0]["date"] if notes else None,
    })

import subprocess, hmac, hashlib, os
WEBHOOK_SECRET = b'ac6872f11b498d88dfb8bb4eb76db74ad7427ad9151377b35aae54cf20ae368c'
GIT_ENV = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -i /root/.ssh/feed_deploy'}
def do_sync():
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'fetch', '--all'], env=GIT_ENV)
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'reset', '--hard', 'origin/main'])
@app.route('/api/webhook', methods=['POST'])
def webhook_sync():
    sig = request.headers.get('X-Hub-Signature-256', '')
    body = request.get_data()
    expected = 'sha256=' + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return jsonify({'error': 'unauthorized'}), 401
    do_sync()
    return jsonify({'status': 'synced'})
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    do_sync()
    return jsonify({'status': 'synced'})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "vault": str(VAULT_PATH), "exists": VAULT_PATH.exists()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)

import subprocess, hmac, hashlib, os

WEBHOOK_SECRET = b'ac6872f11b498d88dfb8bb4eb76db74ad7427ad9151377b35aae54cf20ae368c'
GIT_ENV = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -i /root/.ssh/feed_deploy'}

def do_sync():
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'fetch', '--all'], env=GIT_ENV)
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'reset', '--hard', 'origin/main'])

@app.route('/api/webhook', methods=['POST'])
def webhook_sync():
    sig = request.headers.get('X-Hub-Signature-256', '')
    body = request.get_data()
    expected = 'sha256=' + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return jsonify({'error': 'unauthorized'}), 401
    do_sync()
    return jsonify({'status': 'synced'})

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    do_sync()
    return jsonify({'status': 'synced'})
