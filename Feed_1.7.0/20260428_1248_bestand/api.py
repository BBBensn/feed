#!/usr/bin/env python3
"""
bensn Personal OS – Flask API
Endpoints für Worktracker, Health, Feed
"""

from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
import os
import json
from datetime import datetime, timezone
from functools import wraps

app = Flask(__name__)
CORS(app)

# ── Config ───────────────────────────────────────────────────────────────────
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://bensn:CHANGE_ME_STRONG_PASSWORD@localhost:5432/bensnos"
)
API_KEY = os.environ.get("API_KEY", "CHANGE_ME_API_KEY")


# ── DB Helper ────────────────────────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    return conn


def db_query(sql, params=None, fetchone=False, commit=False):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if commit:
            conn.commit()
            return cur.rowcount
        if fetchone:
            return cur.fetchone()
        return cur.fetchall()
    finally:
        conn.close()


def db_insert(sql, params):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        result = cur.fetchone()
        conn.commit()
        return result
    finally:
        conn.close()


# ── Auth ─────────────────────────────────────────────────────────────────────
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            abort(401, "Invalid API key")
        return f(*args, **kwargs)
    return decorated


# ── Helpers ──────────────────────────────────────────────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat()


def serialize(row):
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
    return d


def serialize_list(rows):
    return [serialize(r) for r in rows]


# ── Health Check ─────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": now_iso()})


# ═══════════════════════════════════════════════════════════════════════════════
# WORKTRACKER – SHIFT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/shift/start", methods=["POST"])
@require_api_key
def shift_start():
    """
    Dienstbeginn eintragen.
    Body: {
        shift_type: "früh"|"nachmittag"|"nacht",
        station: "Puls4",
        service_label: "Puls4 · Nacht",  // optional, für Widget
        is_duo_service: false,
        duo_partner_station: null,
        has_training: false,
        training_note: null,
        work_start: "2026-04-10T22:00:00+02:00"  // optional, default now
    }
    """
    d = request.get_json(force=True)

    required = ["shift_type", "station"]
    for field in required:
        if not d.get(field):
            abort(400, f"Pflichtfeld fehlt: {field}")

    valid_shift_types = ["früh", "nachmittag", "nacht"]
    if d["shift_type"] not in valid_shift_types:
        abort(400, f"shift_type muss einer von {valid_shift_types} sein")

    work_start = d.get("work_start") or now_iso()

    row = db_insert("""
        INSERT INTO shifts (
            work_start, shift_type, station, service_label,
            is_duo_service, duo_partner_station,
            has_training, training_note, source, cafe_puls
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        work_start,
        d["shift_type"],
        d["station"],
        d.get("service_label"),
        d.get("is_duo_service", False),
        d.get("duo_partner_station"),
        d.get("has_training", False),
        d.get("training_note"),
        d.get("source", "shortcut"),
        d.get("cafe_puls", False)
    ))

    return jsonify({"status": "ok", "shift": serialize(row)}), 201


@app.route("/api/shift/end", methods=["POST"])
@require_api_key
def shift_end():
    """
    Dienstende eintragen.
    Body: {
        shift_id: "uuid",           // optional – wenn leer, nimmt aktive Schicht
        work_end: "2026-04-10T...", // optional, default now
        notes: "..."                // optional
    }
    """
    d = request.get_json(force=True)
    work_end = d.get("work_end") or now_iso()

    if d.get("shift_id"):
        shift_id = d["shift_id"]
    else:
        # Aktive Schicht ermitteln
        active = db_query("""
            SELECT id FROM shifts
            WHERE work_end IS NULL
            AND work_start > NOW() - INTERVAL '16 hours'
            ORDER BY work_start DESC LIMIT 1
        """, fetchone=True)
        if not active:
            abort(404, "Keine aktive Schicht gefunden")
        shift_id = active["id"]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE shifts
            SET work_end = %s,
                notes = COALESCE(%s, notes)
            WHERE id = %s
            RETURNING *
        """, (work_end, d.get("notes"), shift_id))
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if not row:
        abort(404, "Schicht nicht gefunden")

    return jsonify({"status": "ok", "shift": serialize(row)})


@app.route("/api/shift/current", methods=["GET"])
@require_api_key
def shift_current():
    """Aktuelle Schicht + Pausen für Widget."""
    row = db_query("SELECT * FROM current_shift", fetchone=True)
    if not row:
        return jsonify({"status": "no_active_shift", "shift": None})

    shift = serialize(row)
    shift_id = shift["id"]

    breaks = db_query("""
        SELECT * FROM breaks
        WHERE shift_id = %s AND (deleted IS NULL OR deleted = false)
        ORDER BY break_start ASC
    """, (shift_id,))

    shift["breaks"] = serialize_list(breaks)
    return jsonify({"status": "ok", "shift": shift})


@app.route("/api/shift/<shift_id>", methods=["GET"])
@require_api_key
def shift_get(shift_id):
    """Einzelne Schicht mit allen Pausen."""
    row = db_query("SELECT * FROM shifts WHERE id = %s", (shift_id,), fetchone=True)
    if not row:
        abort(404, "Schicht nicht gefunden")

    shift = serialize(row)
    breaks = db_query(
        "SELECT * FROM breaks WHERE shift_id = %s AND (deleted IS NULL OR deleted = false) ORDER BY break_start",
        (shift_id,)
    )
    shift["breaks"] = serialize_list(breaks)
    return jsonify(shift)


@app.route("/api/shifts", methods=["GET"])
@require_api_key
def shifts_list():
    """
    Liste der Schichten.
    Query params: limit (default 20), offset (default 0), date (YYYY-MM-DD)
    """
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))
    date_filter = request.args.get("date")

    if date_filter:
        rows = db_query("""
            SELECT * FROM shifts
            WHERE DATE(work_start) = %s AND (deleted IS NULL OR deleted = false)
            ORDER BY work_start DESC
            LIMIT %s OFFSET %s
        """, (date_filter, limit, offset))
    else:
        rows = db_query("""
            SELECT * FROM shifts
            WHERE (deleted IS NULL OR deleted = false)
            ORDER BY work_start DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))

    return jsonify(serialize_list(rows))


@app.route("/api/shift/<shift_id>/correct", methods=["PATCH"])
@require_api_key
def shift_correct(shift_id):
    """
    Schicht korrigieren. Speichert Original-Snapshot in original_data.
    Body: {
        work_start: "...",   // beliebige Felder die geändert werden
        work_end: "...",
        shift_type: "...",
        station: "...",
        notes: "...",
        corrected_reason: "Dienstende vergessen einzutragen"
    }
    """
    d = request.get_json(force=True)

    # Original laden für Snapshot
    original = db_query("SELECT * FROM shifts WHERE id = %s", (shift_id,), fetchone=True)
    if not original:
        abort(404, "Schicht nicht gefunden")

    original_snapshot = serialize(original)

    # Erlaubte Felder zum Korrigieren
    allowed = ["work_start", "work_end", "shift_type", "station",
               "service_label", "is_duo_service", "duo_partner_station",
               "has_training", "training_note", "notes", "cafe_puls"]

    set_clauses = []
    values = []
    for field in allowed:
        if field in d:
            set_clauses.append(f"{field} = %s")
            values.append(d[field])

    if not set_clauses:
        abort(400, "Keine zu korrigierenden Felder angegeben")

    set_clauses += ["corrected = TRUE", "corrected_at = NOW()",
                    "corrected_reason = %s", "original_data = %s"]
    values += [d.get("corrected_reason", "Manuelle Korrektur"),
               json.dumps(original_snapshot), shift_id]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE shifts SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
            values
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "corrected", "shift": serialize(row)})


# ═══════════════════════════════════════════════════════════════════════════════
# WORKTRACKER – BREAK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/break/start", methods=["POST"])
@require_api_key
def break_start():
    """
    Pause beginnen.
    Body: {
        shift_id: "uuid",           // optional – auto-detect aktive Schicht
        break_start: "...",         // optional, default now
        break_type: "Rauchen"
    }
    """
    d = request.get_json(force=True)

    if d.get("shift_id"):
        shift_id = d["shift_id"]
    else:
        active = db_query("""
            SELECT id FROM shifts
            WHERE work_end IS NULL
            AND work_start > NOW() - INTERVAL '16 hours'
            ORDER BY work_start DESC LIMIT 1
        """, fetchone=True)
        if not active:
            abort(404, "Keine aktive Schicht gefunden")
        shift_id = active["id"]

    break_start_ts = d.get("break_start") or now_iso()

    row = db_insert("""
        INSERT INTO breaks (shift_id, break_start, break_type, source)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """, (shift_id, break_start_ts, d.get("break_type", "Pause"), d.get("source", "shortcut")))

    return jsonify({"status": "ok", "break": serialize(row)}), 201


@app.route("/api/break/end", methods=["POST"])
@require_api_key
def break_end():
    """
    Pause beenden.
    Body: {
        break_id: "uuid",           // optional – auto-detect offene Pause
        shift_id: "uuid",           // optional – für auto-detect
        break_end: "...",           // optional, default now
        zig_spicy: 1,
        zig_blend: 0,
        break_type: "Rauchen"       // optional, falls noch nicht gesetzt
    }
    """
    d = request.get_json(force=True)
    break_end_ts = d.get("break_end") or now_iso()

    if d.get("break_id"):
        break_id = d["break_id"]
    else:
        # Offene Pause der aktiven Schicht
        shift_id = d.get("shift_id")
        if not shift_id:
            active = db_query("""
                SELECT id FROM shifts
                WHERE work_end IS NULL
                AND work_start > NOW() - INTERVAL '16 hours'
                ORDER BY work_start DESC LIMIT 1
            """, fetchone=True)
            if not active:
                abort(404, "Keine aktive Schicht gefunden")
            shift_id = active["id"]

        open_break = db_query("""
            SELECT id FROM breaks
            WHERE shift_id = %s AND break_end IS NULL
            ORDER BY break_start DESC LIMIT 1
        """, (shift_id,), fetchone=True)

        if not open_break:
            abort(404, "Keine offene Pause gefunden")
        break_id = open_break["id"]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE breaks
            SET break_end = %s,
                zig_spicy = %s,
                zig_blend = %s,
                break_type = COALESCE(%s, break_type),
                notes = COALESCE(%s, notes)
            WHERE id = %s
            RETURNING *
        """, (
            break_end_ts,
            d.get("zig_spicy", 0),
            d.get("zig_blend", 0),
            d.get("break_type"),
            d.get("notes"),
            break_id
        ))
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if not row:
        abort(404, "Pause nicht gefunden")

    return jsonify({"status": "ok", "break": serialize(row)})


@app.route("/api/break/<break_id>/correct", methods=["PATCH"])
@require_api_key
def break_correct(break_id):
    """Pause korrigieren, analog zu shift_correct."""
    d = request.get_json(force=True)

    original = db_query("SELECT * FROM breaks WHERE id = %s", (break_id,), fetchone=True)
    if not original:
        abort(404, "Pause nicht gefunden")

    original_snapshot = serialize(original)
    allowed = ["break_start", "break_end", "break_type", "zig_spicy", "zig_blend", "notes"]

    set_clauses = []
    values = []
    for field in allowed:
        if field in d:
            set_clauses.append(f"{field} = %s")
            values.append(d[field])

    if not set_clauses:
        abort(400, "Keine zu korrigierenden Felder angegeben")

    set_clauses += ["corrected = TRUE", "corrected_at = NOW()",
                    "corrected_reason = %s", "original_data = %s"]
    values += [d.get("corrected_reason", "Manuelle Korrektur"),
               json.dumps(original_snapshot), break_id]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE breaks SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
            values
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "corrected", "break": serialize(row)})


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/health/sleep", methods=["POST"])
@require_api_key
def log_sleep():
    """
    Schlaf eintragen.
    Body: {
        date: "2026-04-10",
        sleep_start: "2026-04-09T23:00:00+02:00",
        sleep_end: "2026-04-10T07:30:00+02:00",
        duration_minutes: 450,   // alternativ zu start/end
        quality: 4,
        notes: "..."
    }
    """
    d = request.get_json(force=True)

    date = d.get("date") or datetime.now().date().isoformat()

    row = db_insert("""
        INSERT INTO sleep_logs (date, sleep_start, sleep_end, duration_minutes, quality, notes, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date) DO UPDATE SET
            sleep_start = EXCLUDED.sleep_start,
            sleep_end = EXCLUDED.sleep_end,
            duration_minutes = EXCLUDED.duration_minutes,
            quality = EXCLUDED.quality,
            notes = EXCLUDED.notes
        RETURNING *
    """, (
        date,
        d.get("sleep_start"),
        d.get("sleep_end"),
        d.get("duration_minutes"),
        d.get("quality"),
        d.get("notes"),
        d.get("source", "shortcut"),
        d.get("cafe_puls", False)
    ))

    return jsonify({"status": "ok", "sleep": serialize(row)}), 201


@app.route("/api/health/mood", methods=["POST"])
@require_api_key
def log_mood():
    """
    Stimmung eintragen.
    Body: {
        mood_score: 7,
        energy_score: 5,
        anxiety_score: 3,
        tags: ["müde", "gestresst"],
        notes: "...",
        timestamp: "..."    // optional
    }
    """
    d = request.get_json(force=True)

    row = db_insert("""
        INSERT INTO mood_logs (timestamp, mood_score, energy_score, anxiety_score, tags, notes, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        d.get("timestamp") or now_iso(),
        d.get("mood_score"),
        d.get("energy_score"),
        d.get("anxiety_score"),
        d.get("tags", []),
        d.get("notes"),
        d.get("source", "shortcut"),
        d.get("cafe_puls", False)
    ))

    return jsonify({"status": "ok", "mood": serialize(row)}), 201


@app.route("/api/health/log", methods=["POST"])
@require_api_key
def log_health():
    """
    Gesundheitsdaten eintragen (Schritte, Gewicht, Medikamente).
    Body: {
        steps: 8420,
        weight_kg: 78.5,
        medications: [{"name": "Sertralin", "dose_mg": 50, "time": "08:00"}],
        notes: "..."
    }
    """
    d = request.get_json(force=True)

    row = db_insert("""
        INSERT INTO health_logs (timestamp, date, steps, weight_kg, medications, notes, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        d.get("timestamp") or now_iso(),
        d.get("date") or datetime.now().date().isoformat(),
        d.get("steps"),
        d.get("weight_kg"),
        json.dumps(d.get("medications", [])),
        d.get("notes"),
        d.get("source", "shortcut"),
        d.get("cafe_puls", False)
    ))

    return jsonify({"status": "ok", "health": serialize(row)}), 201


# ═══════════════════════════════════════════════════════════════════════════════
# LOCATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/location", methods=["POST"])
@require_api_key
def log_location():
    """
    Standort eintragen. Unterstützt zwei Formate:
    1. OwnTracks HTTP: { "_type": "location", "lat": ..., "lon": ..., "acc": ..., "alt": ..., "tst": ... }
    2. Shortcut: { "latitude": ..., "longitude": ..., "accuracy": ..., "altitude": ... }
    """
    d = request.get_json(force=True)

    # OwnTracks sendet nur _type=location, alles andere ignorieren
    if d.get("_type") and d["_type"] != "location":
        return jsonify({"status": "ignored", "_type": d["_type"]}), 200

    # Feld-Mapping: OwnTracks → intern
    latitude  = d.get("lat")  or d.get("latitude")
    longitude = d.get("lon")  or d.get("longitude")
    accuracy  = d.get("acc")  or d.get("accuracy")
    altitude  = d.get("alt")  or d.get("altitude")
    velocity  = d.get("vel")  or d.get("velocity")
    battery   = d.get("batt") or d.get("battery")

    # OwnTracks liefert Unix-Timestamp in "tst" → in ISO umwandeln
    timestamp = None
    if d.get("tst"):
        from datetime import timezone
        timestamp = datetime.fromtimestamp(d["tst"], tz=timezone.utc).isoformat()
    elif d.get("timestamp"):
        timestamp = d["timestamp"]
    else:
        timestamp = now_iso()

    source = "owntracks" if d.get("_type") == "location" else d.get("source", "shortcut")

    row = db_insert("""
        INSERT INTO location_logs (latitude, longitude, accuracy, altitude, context, source, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        latitude,
        longitude,
        accuracy,
        altitude,
        d.get("context", "auto"),
        source,
        timestamp,
    ))

    return jsonify({"status": "ok", "location": serialize(row)}), 201


@app.route("/api/locations", methods=["GET"])
@require_api_key
def list_locations():
    """
    Standortverlauf abrufen.
    Query params: limit (default 50, max 500), offset (default 0), date (YYYY-MM-DD Vienna time)
    """
    limit  = min(int(request.args.get("limit",  50)), 1000)
    offset = int(request.args.get("offset", 0))
    date_filter = request.args.get("date")

    cols = """id, timestamp, latitude, longitude, accuracy, altitude,
              city, district, country, context, source, velocity, battery, device_id,
              temperature, apparent_temp, precipitation, weather_code, weather_desc,
              cloudcover, windspeed, is_day"""

    if date_filter:
        rows = db_query(f"""
            SELECT {cols}
            FROM location_logs
            WHERE DATE(timestamp AT TIME ZONE 'Europe/Vienna') = %s
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, (date_filter, limit, offset))
        total = db_query("""
            SELECT COUNT(*) AS n FROM location_logs
            WHERE DATE(timestamp AT TIME ZONE 'Europe/Vienna') = %s
        """, (date_filter,), fetchone=True)
    else:
        rows = db_query(f"""
            SELECT {cols}
            FROM location_logs
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        total = db_query("SELECT COUNT(*) AS n FROM location_logs", fetchone=True)

    return jsonify({
        "total": total["n"] if total else 0,
        "limit": limit,
        "offset": offset,
        "locations": serialize_list(rows)
    })


@app.route("/api/stays", methods=["GET"])
@require_api_key
def list_stays():
    """
    Aufenthalte abrufen.
    Query params: limit (default 50), offset (default 0), date (YYYY-MM-DD Vienna time)
    """
    limit  = min(int(request.args.get("limit",  50)), 200)
    offset = int(request.args.get("offset", 0))
    date_filter = request.args.get("date")

    if date_filter:
        rows = db_query("""
            SELECT * FROM location_stays
            WHERE DATE(start_time AT TIME ZONE 'Europe/Vienna') = %s
            ORDER BY start_time DESC
            LIMIT %s OFFSET %s
        """, (date_filter, limit, offset))
    else:
        rows = db_query("""
            SELECT * FROM location_stays
            ORDER BY start_time DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))

    total = db_query("SELECT COUNT(*) AS n FROM location_stays", fetchone=True)

    return jsonify({
        "total": total["n"] if total else 0,
        "limit": limit,
        "offset": offset,
        "stays": serialize_list(rows)
    })


@app.route("/api/stay/<stay_id>", methods=["PATCH"])
@require_api_key
def update_stay(stay_id):
    """
    Stay Name setzen / aktualisieren.
    Body: { "name": "Zuhause" }
    """
    d = request.get_json(force=True)
    name = d.get("name", "").strip() or None

    stay = db_query("SELECT id FROM location_stays WHERE id = %s", (stay_id,), fetchone=True)
    if not stay:
        abort(404, "Stay nicht gefunden")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE location_stays
            SET name = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """, (name, stay_id))
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok", "stay": serialize(row)})


# ═══════════════════════════════════════════════════════════════════════════════
# FEED
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/feed", methods=["GET"])
@require_api_key
def feed():
    """
    Kombinierter Feed aller Aktivitäten.
    Query params: limit (default 50), before (ISO timestamp), types (komma-getrennt)
    """
    limit = min(int(request.args.get("limit", 50)), 200)
    before = request.args.get("before")
    types = request.args.get("types", "").split(",") if request.args.get("types") else None

    items = []

    # Schichten
    if not types or "shift" in types:
        rows = db_query("""
            SELECT 
                s.id, s.work_start AS timestamp, 'shift' AS item_type,
                s.shift_type, s.station, s.service_label,
                s.work_start, s.work_end, s.duration_minutes,
                s.is_duo_service, s.corrected, s.notes,
                COALESCE(b.total_break, 0) AS total_break_minutes,
                COALESCE(b.zig_total, 0) AS zig_total
            FROM shifts s
            LEFT JOIN (
                SELECT shift_id,
                    SUM(duration_minutes) AS total_break,
                    SUM(zig_spicy + zig_blend) AS zig_total
                FROM breaks GROUP BY shift_id
            ) b ON b.shift_id = s.id
            WHERE (%s IS NULL OR s.work_start < %s)
            ORDER BY s.work_start DESC
            LIMIT %s
        """, (before, before, limit))
        items.extend([{**serialize(r), "item_type": "shift"} for r in rows])

    # Mood
    if not types or "mood" in types:
        rows = db_query("""
            SELECT id, timestamp, 'mood' AS item_type,
                   mood_score, energy_score, anxiety_score, tags, notes
            FROM mood_logs
            WHERE (%s IS NULL OR timestamp < %s)
            ORDER BY timestamp DESC LIMIT %s
        """, (before, before, limit))
        items.extend([{**serialize(r), "item_type": "mood"} for r in rows])

    # Sleep
    if not types or "sleep" in types:
        rows = db_query("""
            SELECT id, created_at AS timestamp, 'sleep' AS item_type,
                   date, duration_minutes, quality, notes
            FROM sleep_logs
            WHERE (%s IS NULL OR created_at < %s)
            ORDER BY date DESC LIMIT %s
        """, (before, before, limit))
        items.extend([{**serialize(r), "item_type": "sleep"} for r in rows])

    # Obsidian
    if not types or "obsidian" in types:
        rows = db_query("""
            SELECT id, entry_date AS timestamp, 'obsidian' AS item_type,
                   title, entry_type, content_preview, tags, file_path
            FROM obsidian_entries
            WHERE show_in_feed = TRUE
            AND (%s IS NULL OR entry_date < %s)
            ORDER BY entry_date DESC LIMIT %s
        """, (before, before, limit))
        items.extend([{**serialize(r), "item_type": "obsidian"} for r in rows])

    # Sortieren nach Timestamp
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    items = items[:limit]

    return jsonify({
        "status": "ok",
        "count": len(items),
        "items": items
    })


# ═══════════════════════════════════════════════════════════════════════════════
# STATS / DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/stats/weekly", methods=["GET"])
@require_api_key
def stats_weekly():
    """Wochenübersicht für Grafana / Web."""
    rows = db_query("""
        SELECT * FROM daily_summary
        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY date DESC
    """)
    return jsonify(serialize_list(rows))


@app.route("/api/stats/shift-summary", methods=["GET"])
@require_api_key
def stats_shift_summary():
    """Zusammenfassung nach Schichttypen."""
    rows = db_query("""
        SELECT
            shift_type,
            COUNT(*) AS count,
            ROUND(AVG(duration_minutes)) AS avg_duration_minutes,
            ROUND(AVG(sub.avg_break)) AS avg_break_minutes,
            ROUND(AVG(sub.avg_zig)) AS avg_cigarettes
        FROM shifts s
        LEFT JOIN (
            SELECT shift_id,
                AVG(duration_minutes) AS avg_break,
                AVG(zig_spicy + zig_blend) AS avg_zig
            FROM breaks GROUP BY shift_id
        ) sub ON sub.shift_id = s.id
        WHERE s.work_end IS NOT NULL
        GROUP BY shift_type
        ORDER BY shift_type
    """)
    return jsonify(serialize_list(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e)}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Unauthorized"}), 401

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e)}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500





@app.route("/api/break/add", methods=["POST"])
@require_api_key
def break_add():
    """Pause nachträglich zu einer Schicht hinzufügen."""
    d = request.get_json() or {}
    shift_id = d.get("shift_id")
    if not shift_id:
        return jsonify({"error": "shift_id required"}), 400

    shift = db_query("SELECT id FROM shifts WHERE id = %s AND (deleted IS NULL OR deleted = false)",
                     (shift_id,), fetchone=True)
    if not shift:
        return jsonify({"error": "Shift not found"}), 404

    row = db_insert("""
        INSERT INTO breaks (shift_id, break_start, break_end, break_type, zig_spicy, zig_blend, notes, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        shift_id,
        d.get("break_start"),
        d.get("break_end"),
        d.get("break_type", "Pause"),
        d.get("zig_spicy", 0),
        d.get("zig_blend", 0),
        d.get("notes"),
        d.get("source", "pwa")
    ))

    return jsonify({"break": dict(row)})

@app.route("/api/shift/<shift_id>", methods=["DELETE"])
@require_api_key
def shift_delete(shift_id):
    shift = db_query("SELECT id FROM shifts WHERE id = %s", (shift_id,), fetchone=True)
    if not shift:
        return jsonify({"error": "Shift not found"}), 404
    db_query("UPDATE shifts SET deleted = true WHERE id = %s", (shift_id,), commit=True)
    db_query("UPDATE breaks SET deleted = true WHERE shift_id = %s", (shift_id,), commit=True)
    return jsonify({"status": "deleted", "id": shift_id})


@app.route("/api/break/<break_id>", methods=["DELETE"])
@require_api_key
def break_delete(break_id):
    brk = db_query("SELECT id FROM breaks WHERE id = %s", (break_id,), fetchone=True)
    if not brk:
        return jsonify({"error": "Break not found"}), 404
    db_query("UPDATE breaks SET deleted = true WHERE id = %s", (break_id,), commit=True)
    return jsonify({"status": "deleted", "id": break_id})

# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING — Bestand & Zähler
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/tracking/entries", methods=["GET"])
@require_api_key
def tracking_entries_list():
    """
    Alle Tracking-Einträge.
    Query params: limit (default 200), item_id, category, date (YYYY-MM-DD), entry_type
    """
    limit      = min(int(request.args.get("limit", 200)), 1000)
    item_id    = request.args.get("item_id")
    category   = request.args.get("category")
    date_filter= request.args.get("date")
    entry_type = request.args.get("entry_type")

    conditions = ["(deleted IS NULL OR deleted = false)"]
    params     = []

    if item_id:
        conditions.append("item_id = %s"); params.append(item_id)
    if category:
        conditions.append("category = %s"); params.append(category)
    if date_filter:
        conditions.append("date = %s"); params.append(date_filter)
    if entry_type:
        conditions.append("entry_type = %s"); params.append(entry_type)

    where = " AND ".join(conditions)
    rows = db_query(f"""
        SELECT * FROM tracking_entries
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT %s
    """, params + [limit])

    return jsonify({
        "count":   len(rows),
        "entries": serialize_list(rows)
    })


@app.route("/api/tracking/entry", methods=["POST"])
@require_api_key
def tracking_entry_add():
    """
    Neuen Tracking-Eintrag hinzufügen.
    Body: {
        item_id:    "weed",
        category:   "kiffen",
        name:       "Weed",
        amount:     5.0,
        unit:       "g",
        entry_type: "bestand" | "zaehler",
        date:       "2026-04-21",    // Vienna local date
        note:       "...",           // optional
        source:     "pwa"            // optional
    }
    """
    d = request.get_json(force=True)

    required = ["item_id", "category", "name", "amount", "unit", "entry_type", "date"]
    for field in required:
        if d.get(field) is None:
            abort(400, f"Pflichtfeld fehlt: {field}")

    if d["entry_type"] not in ("bestand", "zaehler", "auffuellung", "entnahme", "delta"):
        abort(400, "entry_type ungültig")

    row = db_insert("""
        INSERT INTO tracking_entries
            (item_id, category, name, amount, unit, entry_type, date, note, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        d["item_id"],
        d["category"],
        d["name"],
        d["amount"],
        d["unit"],
        d["entry_type"],
        d["date"],
        d.get("note"),
        d.get("source", "pwa"),
    ))

    return jsonify({"status": "ok", "entry": serialize(row)}), 201


@app.route("/api/tracking/entry/<entry_id>", methods=["GET"])
@require_api_key
def tracking_entry_get(entry_id):
    """Einzelnen Eintrag abrufen."""
    row = db_query(
        "SELECT * FROM tracking_entries WHERE id = %s AND (deleted IS NULL OR deleted = false)",
        (entry_id,), fetchone=True
    )
    if not row:
        abort(404, "Eintrag nicht gefunden")
    return jsonify(serialize(row))


@app.route("/api/tracking/entry/<entry_id>", methods=["PATCH"])
@require_api_key
def tracking_entry_update(entry_id):
    """
    Eintrag korrigieren.
    Body: { amount, note }  (nur diese zwei Felder erlaubt)
    """
    d = request.get_json(force=True)

    original = db_query(
        "SELECT * FROM tracking_entries WHERE id = %s",
        (entry_id,), fetchone=True
    )
    if not original:
        abort(404, "Eintrag nicht gefunden")

    set_clauses, values = [], []
    if "amount" in d:
        set_clauses.append("amount = %s"); values.append(d["amount"])
    if "note" in d:
        set_clauses.append("note = %s");   values.append(d["note"])
    if not set_clauses:
        abort(400, "Keine Felder zum Aktualisieren")

    values.append(entry_id)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tracking_entries SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
            values
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok", "entry": serialize(row)})


@app.route("/api/tracking/entry/<entry_id>", methods=["DELETE"])
@require_api_key
def tracking_entry_delete(entry_id):
    """Soft-delete."""
    row = db_query(
        "SELECT id FROM tracking_entries WHERE id = %s",
        (entry_id,), fetchone=True
    )
    if not row:
        abort(404, "Eintrag nicht gefunden")

    db_query(
        "UPDATE tracking_entries SET deleted = true WHERE id = %s",
        (entry_id,), commit=True
    )
    return jsonify({"status": "deleted", "id": entry_id})


@app.route("/api/tracking/bestand/<item_id>", methods=["GET"])
@require_api_key
def tracking_bestand(item_id):
    """
    Letzten Bestand + berechneten Verbrauch für ein Item.
    Response: { item_id, latest_amount, latest_date, consumed_since, prev_amount, prev_date }
    """
    rows = db_query("""
        SELECT * FROM tracking_entries
        WHERE item_id = %s AND entry_type = 'bestand'
          AND (deleted IS NULL OR deleted = false)
        ORDER BY timestamp DESC
        LIMIT 2
    """, (item_id,))

    if not rows:
        return jsonify({"item_id": item_id, "latest_amount": None})

    latest = serialize(rows[0])
    result = {
        "item_id":      item_id,
        "latest_amount": latest["amount"],
        "latest_date":   latest["date"],
        "latest_ts":     latest["timestamp"],
        "note":          latest.get("note"),
        "consumed_since": None,
        "prev_amount":   None,
        "prev_date":     None,
    }

    if len(rows) >= 2:
        prev = serialize(rows[1])
        consumed = prev["amount"] - latest["amount"]
        result["prev_amount"]    = prev["amount"]
        result["prev_date"]      = prev["date"]
        result["consumed_since"] = consumed if consumed > 0 else None

    return jsonify(result)


@app.route("/api/tracking/summary", methods=["GET"])
@require_api_key
def tracking_summary():
    """
    Tages-Zusammenfassung der Zähler für die letzten N Tage.
    Query param: days (default 7)
    """
    days = min(int(request.args.get("days", 7)), 90)

    rows = db_query("""
        SELECT
            date,
            item_id,
            name,
            category,
            SUM(amount) AS total_amount,
            unit,
            COUNT(*) AS entry_count
        FROM tracking_entries
        WHERE entry_type = 'zaehler'
          AND (deleted IS NULL OR deleted = false)
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY date, item_id, name, category, unit
        ORDER BY date DESC, category, name
    """, (days,))

    return jsonify({
        "days": days,
        "rows": serialize_list(rows)
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING — Kategorien & Items (Konfiguration)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/tracking/categories", methods=["GET"])
@require_api_key
def tracking_categories_list():
    cats = db_query("""
        SELECT c.*,
               json_agg(
                   json_build_object(
                       'id', i.id, 'slug', i.slug, 'name', i.name,
                       'tracking_mode', i.tracking_mode, 'base_unit', i.base_unit,
                       'unit_size', i.unit_size, 'presets', i.presets,
                       'sort_order', i.sort_order, 'active', i.active,
                       'counter_direction', i.counter_direction,
                       'pack_unit', i.pack_unit, 'pack_size', i.pack_size,
                       'buttons', COALESCE(i.buttons, '[]'::jsonb),
                       'linked_items', COALESCE(i.linked_items, '[]'::jsonb)
                   ) ORDER BY i.sort_order
               ) FILTER (WHERE i.id IS NOT NULL) AS items
        FROM tracking_categories c
        LEFT JOIN tracking_items i ON i.category_id = c.id AND i.active = TRUE
        GROUP BY c.id
        ORDER BY c.sort_order
    """)
    return jsonify({"categories": serialize_list(cats)})


@app.route("/api/tracking/categories", methods=["POST"])
@require_api_key
def tracking_category_add():
    d = request.get_json(force=True)
    if not d.get("name"):
        abort(400, "name fehlt")
    max_order = db_query("SELECT COALESCE(MAX(sort_order),0) AS m FROM tracking_categories", fetchone=True)
    row = db_insert("""
        INSERT INTO tracking_categories (name, emoji, color, sort_order)
        VALUES (%s, %s, %s, %s) RETURNING *
    """, (d["name"].strip(), d.get("emoji", "📦"), d.get("color", "muted"), (max_order["m"] or 0) + 1))
    return jsonify({"status": "ok", "category": serialize(row)}), 201


@app.route("/api/tracking/categories/<cat_id>", methods=["PATCH"])
@require_api_key
def tracking_category_update(cat_id):
    d = request.get_json(force=True)
    allowed = ["name", "emoji", "color", "sort_order"]
    clauses, vals = [], []
    for f in allowed:
        if f in d:
            clauses.append(f"{f} = %s"); vals.append(d[f])
    if not clauses:
        abort(400, "Nichts zu ändern")
    vals.append(cat_id)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE tracking_categories SET {', '.join(clauses)} WHERE id = %s RETURNING *", vals)
        row = cur.fetchone(); conn.commit()
    finally:
        conn.close()
    if not row: abort(404)
    return jsonify({"status": "ok", "category": serialize(row)})


@app.route("/api/tracking/categories/<cat_id>", methods=["DELETE"])
@require_api_key
def tracking_category_delete(cat_id):
    items = db_query("SELECT COUNT(*) AS n FROM tracking_items WHERE category_id = %s AND active = TRUE", (cat_id,), fetchone=True)
    if items and items["n"] > 0:
        abort(400, "Kategorie hat noch aktive Items")
    db_query("DELETE FROM tracking_categories WHERE id = %s", (cat_id,), commit=True)
    return jsonify({"status": "deleted", "id": cat_id})


@app.route("/api/tracking/items", methods=["POST"])
@require_api_key
def tracking_item_add():
    import re
    d = request.get_json(force=True)
    for f in ["category_id", "name", "base_unit"]:
        if not d.get(f):
            abort(400, f"{f} fehlt")
    max_order = db_query(
        "SELECT COALESCE(MAX(sort_order),0) AS m FROM tracking_items WHERE category_id = %s",
        (d["category_id"],), fetchone=True
    )
    slug = d.get("slug") or re.sub(r'[^a-z0-9]+', '-', d["name"].lower()).strip('-')
    existing = db_query("SELECT id FROM tracking_items WHERE slug = %s", (slug,), fetchone=True)
    if existing:
        slug = slug + "-" + str(int(datetime.now().timestamp()))[-4:]
    row = db_insert("""
        INSERT INTO tracking_items
            (category_id, slug, name, tracking_mode, base_unit, unit_size, presets,
             counter_direction, pack_unit, pack_size, buttons, linked_items, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
    """, (
        d["category_id"], slug, d["name"].strip(),
        d.get("tracking_mode", "zaehler"), d["base_unit"].strip(),
        float(d.get("unit_size", 1)), d.get("presets", ""),
        d.get("counter_direction", "+"),
        d.get("pack_unit") or None,
        float(d["pack_size"]) if d.get("pack_size") else None,
        json.dumps(d.get("buttons", [])),
        json.dumps(d.get("linked_items", [])),
        (max_order["m"] or 0) + 1,
    ))
    return jsonify({"status": "ok", "item": serialize(row)}), 201


@app.route("/api/tracking/items/<item_id>", methods=["PATCH"])
@require_api_key
def tracking_item_update(item_id):
    d = request.get_json(force=True)
    allowed = ["name", "tracking_mode", "base_unit", "unit_size", "presets",
               "counter_direction", "pack_unit", "pack_size", "buttons", "linked_items",
               "sort_order", "active", "category_id"]
    clauses, vals = [], []
    for f in allowed:
        if f in d:
            val = d[f]
            # JSONB fields need json.dumps
            if f in ("buttons", "linked_items"):
                val = json.dumps(val) if not isinstance(val, str) else val
            clauses.append(f"{f} = %s"); vals.append(val)
    if not clauses:
        abort(400, "Nichts zu ändern")
    vals.append(item_id)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE tracking_items SET {', '.join(clauses)} WHERE id = %s RETURNING *", vals)
        row = cur.fetchone(); conn.commit()
    finally:
        conn.close()
    if not row: abort(404)
    return jsonify({"status": "ok", "item": serialize(row)})


@app.route("/api/tracking/items/<item_id>", methods=["DELETE"])
@require_api_key
def tracking_item_delete(item_id):
    db_query("UPDATE tracking_items SET active = FALSE WHERE id = %s", (item_id,), commit=True)
    return jsonify({"status": "deleted", "id": item_id})


@app.route("/api/tracking/entries/batch", methods=["POST"])
@require_api_key
def tracking_entries_batch():
    """
    Mehrere Einträge auf einmal buchen (für verknüpfte Items).
    Body: { "entries": [ {item_id, category, name, amount, unit, entry_type, date}, ... ] }
    """
    d = request.get_json(force=True)
    entries = d.get("entries", [])
    if not entries:
        abort(400, "entries fehlt")

    results = []
    for e in entries:
        for f in ["item_id", "category", "name", "amount", "unit", "entry_type", "date"]:
            if e.get(f) is None:
                abort(400, f"Pflichtfeld fehlt: {f}")
        row = db_insert("""
            INSERT INTO tracking_entries
                (item_id, category, name, amount, unit, entry_type, date, note, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            e["item_id"], e["category"], e["name"], e["amount"],
            e["unit"], e["entry_type"], e["date"],
            e.get("note"), e.get("source", "pwa"),
        ))
        results.append(serialize(row))

    return jsonify({"status": "ok", "count": len(results), "entries": results}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
