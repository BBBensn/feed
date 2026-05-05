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
    Standort eintragen (iPhone Shortcut).
    Body: {
        latitude: 48.1925,
        longitude: 16.3897,
        accuracy: 10.0,
        altitude: 180.0,
        context: "work"
    }
    """
    d = request.get_json(force=True)

    row = db_insert("""
        INSERT INTO location_logs (latitude, longitude, accuracy, altitude, context, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        d.get("latitude"),
        d.get("longitude"),
        d.get("accuracy"),
        d.get("altitude"),
        d.get("context", "other"),
        d.get("source", "shortcut"),
        d.get("cafe_puls", False)
    ))

    return jsonify({"status": "ok", "location": serialize(row)}), 201


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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
