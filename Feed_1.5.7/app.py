#!/usr/bin/env python3
"""Bensn-Feed API — liest Obsidian .md Notes aus 01_Journal und gibt sie als JSON zurück."""

import os
import re
import subprocess
import hmac
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
import frontmatter
from PIL import Image, ImageOps
import io

from pillow_heif import register_heif_opener
register_heif_opener()

app = Flask(__name__)

VAULT_PATH = Path("/var/www/feed/vault/01_Journal")
UPLOAD_PATH = Path("/var/www/feed/public/uploads")
UPLOAD_URL_BASE = "https://feed.bensn.me/uploads"
WEBHOOK_SECRET = b'ac6872f11b498d88dfb8bb4eb76db74ad7427ad9151377b35aae54cf20ae368c'
UPLOAD_API_KEY = '3dbdb54401dd731f5e454053cd64606f6978986a8312bdab991bf9264210d152'
GIT_ENV = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -i /root/.ssh/feed_deploy'}

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

# ── Sync ──────────────────────────────────────────────────────────────────────

def do_sync():
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'fetch', '--all'], env=GIT_ENV)
    subprocess.run(['git', '-C', '/var/www/feed/vault', 'reset', '--hard', 'origin/main'])

# ── Image processing ──────────────────────────────────────────────────────────

def process_image(file_data, max_size=2048, quality=85):
    img = Image.open(io.BytesIO(file_data))
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format='JPEG', quality=quality, optimize=True)
    return out.getvalue()

# ── Note helpers ──────────────────────────────────────────────────────────────

def parse_date(val):
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
    images = []
    for m in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", content):
        images.append({"alt": m.group(1), "url": m.group(2)})
    return images

def extract_media_links(content):
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

def load_note(path: Path, folder: str):
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None
    meta = post.metadata
    content = (post.content or "").strip()
    note_type = str(meta.get("type", "")).lower() or folder.lower()
    dt = parse_date(meta.get("date_created")) or date_from_filename(path.stem)
    if not dt:
        return None
    title = re.sub(r"^\d{4}-\d{2}-\d{2}(-\d{4})?-?", "", path.stem).replace("-", " ").strip()
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
    notes = []
    if not VAULT_PATH.exists():
        return notes
    for md_file in VAULT_PATH.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        note = load_note(md_file, md_file.parent.name)
        if note:
            notes.append(note)
    notes.sort(key=lambda n: n["date"], reverse=True)
    return notes

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/feed")
def feed():
    notes = load_all_notes()
    type_filter = request.args.get("type", "").lower()
    if type_filter:
        notes = [n for n in notes if n["type"] == type_filter]
    folder_filter = request.args.get("folder", "").lower()
    if folder_filter:
        notes = [n for n in notes if n["folder"].lower() == folder_filter]
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    return jsonify({"count": len(notes[:limit]), "notes": notes[:limit]})

@app.route("/api/feed/stats")
def stats():
    notes = load_all_notes()
    by_type, by_folder = {}, {}
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

@app.route("/api/feed/<note_id>")
def single_note(note_id):
    for md_file in VAULT_PATH.rglob("*.md"):
        if md_file.stem == note_id:
            note = load_note(md_file, md_file.parent.name)
            if note:
                return jsonify(note)
    return jsonify({"error": "Note not found"}), 404

@app.route("/api/upload", methods=["POST"])
def upload():
    """POST /api/upload
    Header: X-API-Key: <key>
    Body: multipart/form-data (field 'file', beliebiger Name) ODER roher Bild-Body
    Returns: URL(s) als plain text, eine pro Zeile
    """
    key = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(key, UPLOAD_API_KEY):
        return jsonify({"error": "unauthorized"}), 401

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    urls = []

    # Variante 1: multipart/form-data (beliebiger Feldname)
    if request.files:
        files = list(request.files.values())
        for f in files:
            try:
                data = f.read()
                if not data:
                    continue
                jpeg_data = process_image(data)
                rand = secrets.token_hex(4)
                filename = f"{timestamp}-{rand}.jpg"
                (UPLOAD_PATH / filename).write_bytes(jpeg_data)
                urls.append(f"{UPLOAD_URL_BASE}/{filename}")
            except Exception as e:
                return jsonify({"error": f"processing failed: {str(e)}"}), 500
        if urls:
            return "\n".join(urls), 200, {"Content-Type": "text/plain"}

    # Variante 2: roher Bild-Body (Shortcuts sendet manchmal so)
    raw = request.get_data()
    if raw:
        try:
            jpeg_data = process_image(raw)
            rand = secrets.token_hex(4)
            filename = f"{timestamp}-{rand}.jpg"
            (UPLOAD_PATH / filename).write_bytes(jpeg_data)
            return f"{UPLOAD_URL_BASE}/{filename}", 200, {"Content-Type": "text/plain"}
        except Exception as e:
            return jsonify({"error": f"processing failed: {str(e)}"}), 500

    return jsonify({"error": "no image data provided"}), 400

@app.route("/api/webhook", methods=["POST"])
def webhook_sync():
    sig = request.headers.get("X-Hub-Signature-256", "")
    body = request.get_data()
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return jsonify({"error": "unauthorized"}), 401
    do_sync()
    return jsonify({"status": "synced"})

@app.route("/api/sync", methods=["POST"])
def manual_sync():
    do_sync()
    return jsonify({"status": "synced"})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "vault": str(VAULT_PATH), "exists": VAULT_PATH.exists()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
