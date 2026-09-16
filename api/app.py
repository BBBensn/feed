#!/usr/bin/env python3
"""Bensn-Feed API — liest Obsidian .md Notes aus 01_Journal und gibt sie als JSON zurück."""

import os
import re
import json
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
import psycopg2
import psycopg2.extras

app = Flask(__name__)

# ── PostgreSQL connection ──────────────────────────────────────────────────────
DB_URL = os.environ.get('DATABASE_URL', '')

def get_db():
    """Get a database connection. Caller is responsible for closing."""
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

VAULT_PATH = Path("/var/www/feed/vault/01_Journal")
UPLOAD_PATH = Path("/var/www/feed/public/uploads")
UPLOAD_URL_BASE = "https://feed.bensn.me/uploads"
SHARE_CONFIG_PATH = Path("/var/www/feed/share_config.json")
WEBHOOK_SECRET = b'ac6872f11b498d88dfb8bb4eb76db74ad7427ad9151377b35aae54cf20ae368c'
UPLOAD_API_KEY = '3dbdb54401dd731f5e454053cd64606f6978986a8312bdab991bf9264210d152'
GIT_ENV = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -i /root/.ssh/feed_deploy'}

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

# ── Share config ───────────────────────────────────────────────────────────────

DEFAULT_SHARE_CONFIG = {
    "shared_types": ["diary", "mood", "reflexion", "reflexionen", "therapie", "symptome", "symptom"],
    "blocked_types": ["fit", "fits", "arbeit", "idea", "ideas", "project_log", "projectlog", "wortwurzel"]
}

def load_share_config():
    if SHARE_CONFIG_PATH.exists():
        try:
            return json.loads(SHARE_CONFIG_PATH.read_text())
        except Exception:
            pass
    return DEFAULT_SHARE_CONFIG

def is_note_shared(note: dict, config: dict) -> bool:
    """Returns True if this note should appear in the shared feed."""
    # Explicit private flag in frontmatter overrides everything
    meta = note.get("meta", {})
    if str(meta.get("private", "")).lower() in ("true", "1", "yes"):
        return False
    # Type must be in shared_types
    note_type = (note.get("type") or "").lower()
    shared = [t.lower() for t in config.get("shared_types", [])]
    blocked = [t.lower() for t in config.get("blocked_types", [])]
    if note_type in blocked:
        return False
    if note_type in shared:
        return True
    return False

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

@app.route("/api/feed/shared")
def feed_shared():
    """Public shared feed — filtered by share_config.json + private frontmatter flag."""
    config = load_share_config()
    notes = load_all_notes()
    shared = [n for n in notes if is_note_shared(n, config)]
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500
    return jsonify({"count": len(shared[:limit]), "notes": shared[:limit]})

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

@app.route("/api/share/config", methods=["GET"])
def share_config_get():
    """Get current sharing config."""
    return jsonify(load_share_config())

@app.route("/api/share/config", methods=["POST"])
def share_config_post():
    """Update sharing config. Requires X-API-Key."""
    key = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(key, UPLOAD_API_KEY):
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "invalid json"}), 400
    SHARE_CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return jsonify({"status": "saved", "config": data})

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

    # Variante 2: roher Bild-Body
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

import urllib.request as _urllib_req

@app.route('/api/oembed')
def oembed_proxy():
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'no url'}), 400
    if 'spotify.com' in url:
        api_url = 'https://open.spotify.com/oembed?url=' + url
    elif 'youtube.com' in url or 'youtu.be' in url:
        api_url = 'https://www.youtube.com/oembed?url=' + url + '&format=json'
    else:
        return jsonify({'error': 'unsupported'}), 400
    try:
        req = _urllib_req.Request(api_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept': 'application/json, */*'})
        with _urllib_req.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 502


# ── Worktracker integration ────────────────────────────────────────────────────

def utc_to_vienna_naive(iso_str):
    """Convert a UTC ISO string to naive Vienna local ISO string for consistent sorting with note dates."""
    if not iso_str:
        return iso_str
    from datetime import timezone, timedelta
    s = str(iso_str)
    # Parse UTC timestamp
    s_clean = s.replace('+00:00', '').replace('Z', '')
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            from datetime import datetime
            dt = datetime.strptime(s_clean, fmt)
            break
        except ValueError:
            continue
    else:
        return iso_str  # can't parse, return as-is
    # Vienna is UTC+1 (winter) or UTC+2 (summer)
    # Use simple DST approximation: last Sunday March - last Sunday October = CEST (UTC+2)
    year = dt.year
    # Last Sunday in March
    import calendar
    def last_sunday(y, m):
        last_day = calendar.monthrange(y, m)[1]
        day = last_day
        from datetime import date
        while date(y, m, day).weekday() != 6:
            day -= 1
        return day
    dst_start = (year, 3, last_sunday(year, 3), 2)   # 02:00 UTC
    dst_end   = (year, 10, last_sunday(year, 10), 1)  # 01:00 UTC
    from datetime import datetime
    in_dst = (
        datetime(year, dst_start[1], dst_start[2], dst_start[3]) <= dt <
        datetime(year, dst_end[1], dst_end[2], dst_end[3])
    )
    offset_hours = 2 if in_dst else 1
    vienna_dt = dt + timedelta(hours=offset_hours)
    return vienna_dt.strftime('%Y-%m-%dT%H:%M:%S')

def shift_to_events(shift, breaks, include_details=True):
    """Convert one shift + its breaks into feed events."""
    events = []
    sid = shift.get('id', '')
    station = shift.get('station', '—')
    stype = shift.get('shift_type', '')
    total_break = sum((b.get('duration_minutes') or 0) for b in breaks if b.get('break_end'))
    netto = (shift.get('duration_minutes') or 0) - total_break

    if shift.get('work_start'):
        ev = {
            'id': f'shift-start-{sid}',
            'type': 'work_start',
            'date': utc_to_vienna_naive(shift['work_start']),
            'shift_id': sid,
            'station': station,
            'shift_type': stype,
        }
        if include_details:
            ev['notes'] = shift.get('notes')
            ev['cafe_puls'] = shift.get('cafe_puls', False)
            ev['duo_partner_station'] = shift.get('duo_partner_station')
        events.append(ev)

    for b in breaks:
        if not b.get('break_start') or b.get('deleted'):
            continue
        ev = {
            'id': f'shift-pause-{b["id"]}',
            'type': 'work_pause',
            'date': utc_to_vienna_naive(b['break_start']),
            'shift_id': sid,
            'station': station,
            'shift_type': stype,
            'break_type': b.get('break_type', 'Pause'),
            'duration_minutes': b.get('duration_minutes'),
        }
        if include_details:
            ev['zig_spicy'] = b.get('zig_spicy', 0)
            ev['zig_blend'] = b.get('zig_blend', 0)
            ev['notes'] = b.get('notes')
        events.append(ev)

    if shift.get('work_end'):
        ev = {
            'id': f'shift-end-{sid}',
            'type': 'work_end',
            'date': utc_to_vienna_naive(shift['work_end']),
            'shift_id': sid,
            'station': station,
            'shift_type': stype,
            'netto_minutes': netto,
            'total_break_minutes': total_break,
        }
        if include_details:
            ev['zig_spicy'] = sum((b.get('zig_spicy') or 0) for b in breaks)
            ev['zig_blend'] = sum((b.get('zig_blend') or 0) for b in breaks)
            ev['notes'] = shift.get('notes')
        events.append(ev)

    return events


WORKTRACKER_API_KEY = 'a9b571df1b237992f87e1126411403ff1ab57cf9aa9b9829015e4c842be8c6f5'
WORKTRACKER_BASE = 'http://localhost:5001'

def _wt_get(path):
    """Internal GET to worktracker API with auth."""
    import urllib.request as _req
    req = _req.Request(
        f'{WORKTRACKER_BASE}{path}',
        headers={'X-API-Key': WORKTRACKER_API_KEY}
    )
    with _req.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())

def fetch_shift_events(limit=100, include_details=True):
    """Fetch shifts from worktracker and convert to feed events."""
    try:
        data = _wt_get(f'/api/shifts?limit={limit}')
        shifts = data if isinstance(data, list) else data.get('shifts', [])
    except Exception:
        return []

    events = []
    for shift in shifts:
        if shift.get('deleted'):
            continue
        breaks = []
        try:
            detail = _wt_get(f'/api/shift/{shift["id"]}')
            breaks = [b for b in (detail.get('breaks') or []) if not b.get('deleted')]
        except Exception:
            pass
        events.extend(shift_to_events(shift, breaks, include_details=include_details))

    return events


# ── Health integration ───────────────────────────────────────────────────────
# health.bensn.me's tables live in the same Postgres DB feed-api already connects to
# (for the `shares` table) — reading them directly avoids adding a second cross-service
# HTTP-call pattern alongside the existing worktracker one.

def fetch_medication_events(limit=100):
    """Fetch recent medication intakes and convert to feed events."""
    if not DB_URL:
        return []
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT l.id, l.taken_at, m.name AS medication_name, m.dose_mg
            FROM health_medication_logs l
            JOIN health_medications m ON m.id = l.medication_id
            WHERE l.deleted = FALSE
            ORDER BY l.taken_at DESC LIMIT %s
        ''', (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return []

    return [{
        'id': f'medication-{r["id"]}',
        'type': 'medication_taken',
        'date': utc_to_vienna_naive(r['taken_at'].isoformat()),
        'medication_name': r['medication_name'],
        'dose_mg': float(r['dose_mg']) if r['dose_mg'] is not None else None,
    } for r in rows]


def fetch_bp_events(limit=100):
    """Fetch recent blood pressure readings and convert to feed events."""
    if not DB_URL:
        return []
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, measured_at, systolic, diastolic, pulse
            FROM health_bp_logs WHERE deleted = FALSE
            ORDER BY measured_at DESC LIMIT %s
        ''', (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return []

    return [{
        'id': f'bp-{r["id"]}',
        'type': 'bp_reading',
        'date': utc_to_vienna_naive(r['measured_at'].isoformat()),
        'systolic': r['systolic'],
        'diastolic': r['diastolic'],
        'pulse': r['pulse'],
    } for r in rows]


def fetch_meal_events(limit=100):
    """Fetch recent meals and convert to feed events."""
    if not DB_URL:
        return []
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, eaten_at, label, description
            FROM health_meals WHERE deleted = FALSE
            ORDER BY eaten_at DESC LIMIT %s
        ''', (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return []

    return [{
        'id': f'meal-{r["id"]}',
        'type': 'meal_logged',
        'date': utc_to_vienna_naive(r['eaten_at'].isoformat()),
        'label': r['label'],
        'description': r['description'],
    } for r in rows]


@app.route("/api/feed/combined")
def feed_combined():
    """Private combined feed: Obsidian notes + native journal entries + worktracker +
    health events. Health events are intentionally NOT included in feed_combined_shared()
    below — medical data has no business appearing on a link shared with other people."""
    notes = load_all_notes() + fetch_journal_events(limit=200)
    events = fetch_shift_events(limit=100, include_details=True)
    events += fetch_medication_events(limit=100)
    events += fetch_bp_events(limit=100)
    events += fetch_meal_events(limit=100)
    combined = notes + events
    combined.sort(key=lambda x: x.get('date') or '', reverse=True)
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500
    return jsonify({"count": len(combined[:limit]), "notes": combined[:limit]})


@app.route("/api/feed/combined/shared")
def feed_combined_shared():
    """Public combined feed: shared notes + worktracker events (no details)."""
    config = load_share_config()
    notes = load_all_notes() + fetch_journal_events(limit=200)
    shared_notes = [n for n in notes if is_note_shared(n, config)]
    events = fetch_shift_events(limit=100, include_details=False)
    combined = shared_notes + events
    combined.sort(key=lambda x: x.get('date') or '', reverse=True)
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500
    return jsonify({"count": len(combined[:limit]), "notes": combined[:limit]})


# ── Wikilink extraction ───────────────────────────────────────────────────────

def extract_wikilinks(content):
    """Extract all [[Link]] references from note content."""
    return re.findall(r'\[\[([^\]]+)\]\]', content or '')

def note_has_blocked_wikilink(note, blocked):
    """Returns True if note contains any blocked wikilink (case-insensitive)."""
    if not blocked:
        return False
    blocked_lower = [b.lower().strip() for b in blocked]
    links = extract_wikilinks(note.get('content', ''))
    # Also check title
    links.append(note.get('title', '') or '')
    for link in links:
        # Handle [[Link|Alias]] format
        link_name = link.split('|')[0].strip().lower()
        if link_name in blocked_lower:
            return True
    return False

def apply_share_filters(notes_and_events, share):
    """Filter a combined list of notes+events by share config."""
    result = []
    allowed_types = [t.lower() for t in (share.get('allowed_types') or [])]
    blocked_types = [t.lower() for t in (share.get('blocked_types') or [])]
    blocked_wikilinks = share.get('blocked_wikilinks') or []
    date_from = share.get('date_from')
    date_to = share.get('date_to')
    include_work = share.get('include_work', True)

    for item in notes_and_events:
        itype = (item.get('type') or '').lower()
        is_work = itype in ('work_start', 'work_pause', 'work_end')

        # Work events: check include_work flag
        if is_work and not include_work:
            continue

        # Type filters (only for notes, not work events)
        if not is_work:
            if allowed_types and itype not in allowed_types:
                continue
            if blocked_types and itype in blocked_types:
                continue
            # private: true frontmatter always blocked
            meta = item.get('meta', {})
            if str(meta.get('private', '')).lower() in ('true', '1', 'yes'):
                continue

        # Date range filter
        item_date_str = (item.get('date') or '')[:10]
        if date_from and item_date_str < str(date_from):
            continue
        if date_to and item_date_str > str(date_to):
            continue

        # Wikilink filter (only for notes)
        if not is_work and note_has_blocked_wikilink(item, blocked_wikilinks):
            continue

        result.append(item)

    return result

# ── Share endpoints ───────────────────────────────────────────────────────────

def strip_note_details(note):
    """Remove sensitive details for shared view (same as combined/shared)."""
    is_work = (note.get('type') or '').startswith('work_')
    if is_work:
        n = {k: v for k, v in note.items()
             if k not in ('zig_spicy', 'zig_blend', 'notes', 'cafe_puls', 'duo_partner_station')}
        return n
    return note

@app.route('/api/share/<token>')
def share_feed(token):
    """Public share feed — filtered by share config for this token."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM shares WHERE token = %s AND active = true',
            (token,)
        )
        share = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503

    if not share:
        return jsonify({'error': 'not found'}), 404

    share = dict(share)

    # Load all notes + work events
    config = load_share_config()
    notes = load_all_notes() + fetch_journal_events(limit=200)
    # Use share's allowed/blocked types to filter — if none set, use global shared_types
    if not share.get('allowed_types') and not share.get('blocked_types'):
        notes = [n for n in notes if is_note_shared(n, config)]

    work_events = []
    if share.get('include_work', True):
        work_events = fetch_shift_events(limit=200, include_details=False)

    combined = notes + work_events
    combined.sort(key=lambda x: x.get('date') or '', reverse=True)

    filtered = apply_share_filters(combined, share)
    stripped = [strip_note_details(n) for n in filtered]

    return jsonify({
        'label': share['label'],
        'count': len(stripped),
        'notes': stripped,
        'date_from': str(share['date_from']) if share['date_from'] else None,
        'date_to': str(share['date_to']) if share['date_to'] else None,
    })


@app.route('/api/shares', methods=['GET'])
def list_shares():
    """Admin: list all shares. Requires Basic Auth (via Nginx)."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT * FROM shares ORDER BY created_at DESC')
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        # Serialize dates
        for r in rows:
            for k in ('date_from', 'date_to', 'created_at'):
                if r.get(k):
                    r[k] = str(r[k])
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/shares', methods=['POST'])
def create_share():
    """Admin: create a new share."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    data = request.get_json()
    if not data or not data.get('label'):
        return jsonify({'error': 'label required'}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        import secrets as _secrets
        token = _secrets.token_urlsafe(24)
        cur.execute(
            """INSERT INTO shares
               (token, label, allowed_types, blocked_types, blocked_wikilinks,
                date_from, date_to, include_work, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
               RETURNING *""",
            (
                token,
                data['label'],
                data.get('allowed_types') or None,
                data.get('blocked_types') or None,
                data.get('blocked_wikilinks') or None,
                data.get('date_from') or None,
                data.get('date_to') or None,
                data.get('include_work', True),
            )
        )
        row = dict(cur.fetchone())
        conn.commit()
        cur.close()
        conn.close()
        for k in ('date_from', 'date_to', 'created_at'):
            if row.get(k):
                row[k] = str(row[k])
        return jsonify(row), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/shares/<share_id>', methods=['PATCH'])
def update_share(share_id):
    """Admin: update a share."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    data = request.get_json()
    if not data:
        return jsonify({'error': 'no data'}), 400
    fields = []
    values = []
    allowed_fields = {
        'label', 'allowed_types', 'blocked_types', 'blocked_wikilinks',
        'date_from', 'date_to', 'include_work', 'active'
    }
    for k, v in data.items():
        if k in allowed_fields:
            fields.append(f'{k} = %s')
            values.append(v if v != '' else None)
    if not fields:
        return jsonify({'error': 'no valid fields'}), 400
    values.append(share_id)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            f'UPDATE shares SET {", ".join(fields)} WHERE id = %s RETURNING *',
            values
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'not found'}), 404
        row = dict(row)
        for k in ('date_from', 'date_to', 'created_at'):
            if row.get(k):
                row[k] = str(row[k])
        return jsonify(row)
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/shares/<share_id>', methods=['DELETE'])
def delete_share(share_id):
    """Admin: hard-delete a share."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM shares WHERE id = %s RETURNING id', (share_id,))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'not found'}), 404
        return jsonify({'status': 'deleted', 'id': share_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/wikilinks')
def get_wikilinks():
    """Admin: return all unique wikilinks from the vault for autocomplete."""
    links = set()
    if VAULT_PATH.exists():
        for md_file in VAULT_PATH.rglob('*.md'):
            try:
                text = md_file.read_text(errors='ignore')
                for m in re.finditer(r'\[\[([^\]]+)\]\]', text):
                    link = m.group(1).split('|')[0].strip()
                    if link:
                        links.add(link)
            except Exception:
                pass
    return jsonify(sorted(links))


# ── Journal entries (native replacement for Obsidian-authored notes) ─────────────
# Starts with 'mood' only (see CLAUDE.md) — the other 8 entry_type values are allowed by
# the schema's CHECK constraint already, but this API doesn't discriminate by type; any
# type-specific validation lives in the frontend compose form for now.

JOURNAL_TYPE_COLORS = {
    'diary': '#e5b181', 'mood': '#b8ebd0', 'reflexion': '#ffb400',
    'symptome': '#f96f5d', 'therapie': '#9c3848', 'fits': '#C9B6BE',
    'arbeit': '#065143', 'ideas': '#6622cc', 'project_log': '#1d4e89',
}

def journal_row_to_note(row):
    """Shape a journal_entries row like an Obsidian-note dict so the existing feed
    renderer (which reads note.type/title/content/date/tags) handles both transparently."""
    row = dict(row)
    return {
        'id': f"journal-{row['id']}",
        'db_id': str(row['id']),
        'type': row['entry_type'],
        'folder': row['entry_type'],
        'title': row.get('title'),
        'date': utc_to_vienna_naive(row['entry_date'].isoformat()) if row.get('entry_date') else None,
        'date_modified': row['updated_at'].isoformat() if row.get('updated_at') else None,
        'tags': row.get('tags') or [],
        'content': row.get('body') or '',
        'images': row.get('images') or [],
        'media_links': [],
        'meta': row.get('fields') or {},
        'path': None,
    }


def fetch_journal_events(limit=200):
    if not DB_URL:
        return []
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM journal_entries WHERE deleted = FALSE '
            'ORDER BY entry_date DESC LIMIT %s',
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return []
    return [journal_row_to_note(r) for r in rows]


@app.route('/api/journal/entries', methods=['GET'])
def list_journal_entries():
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    entry_type = request.args.get('type')
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        limit, offset = 100, 0
    sql = 'SELECT * FROM journal_entries WHERE deleted = FALSE'
    params = []
    if entry_type:
        sql += ' AND entry_type = %s'
        params.append(entry_type)
    sql += ' ORDER BY entry_date DESC LIMIT %s OFFSET %s'
    params += [limit, offset]
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    return jsonify([journal_row_to_note(r) for r in rows])


@app.route('/api/journal/entry', methods=['POST'])
def create_journal_entry():
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    d = request.get_json(force=True)
    if not d.get('entry_type'):
        return jsonify({'error': 'entry_type required'}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO journal_entries
                   (entry_type, entry_date, title, body, tags, fields, images, source)
               VALUES (%s, COALESCE(%s, NOW()), %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (d['entry_type'], d.get('entry_date'), d.get('title'), d.get('body'),
             d.get('tags', []), json.dumps(d.get('fields', {})), d.get('images', []),
             d.get('source', 'web'))
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    return jsonify(journal_row_to_note(row)), 201


@app.route('/api/journal/entry/<entry_id>', methods=['PATCH'])
def update_journal_entry(entry_id):
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    d = request.get_json(force=True)
    allowed = ['entry_date', 'title', 'body', 'tags', 'images']
    fields, values = [], []
    for k in allowed:
        if k in d:
            fields.append(f'{k} = %s')
            values.append(d[k])
    if 'fields' in d:
        fields.append('fields = %s')
        values.append(json.dumps(d['fields']))
    if not fields:
        return jsonify({'error': 'no valid fields'}), 400
    fields.append('updated_at = NOW()')
    values.append(entry_id)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            f'UPDATE journal_entries SET {", ".join(fields)} WHERE id = %s RETURNING *',
            values
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(journal_row_to_note(row))


@app.route('/api/journal/entry/<entry_id>', methods=['DELETE'])
def delete_journal_entry(entry_id):
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'UPDATE journal_entries SET deleted = TRUE WHERE id = %s RETURNING id',
            (entry_id,)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'status': 'deleted', 'id': entry_id})


@app.route('/api/journal/mood-summary', methods=['GET'])
def journal_mood_summary():
    """Recent mood trend (valenz over time) for dashboards to consume."""
    if not DB_URL:
        return jsonify({'error': 'DB not configured'}), 503
    try:
        limit = int(request.args.get('limit', 30))
    except ValueError:
        limit = 30
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """SELECT entry_date, fields->>'valenz' AS valenz FROM journal_entries
               WHERE entry_type = 'mood' AND deleted = FALSE
               ORDER BY entry_date DESC LIMIT %s""",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    return jsonify([
        {'date': r['entry_date'].isoformat(), 'valenz': int(r['valenz']) if r['valenz'] is not None else None}
        for r in rows
    ])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
