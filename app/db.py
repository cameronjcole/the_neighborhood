"""SQLite access. All SQL lives here so the backend can be swapped (e.g. Supabase Postgres) later."""
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    address TEXT,
    timezone TEXT NOT NULL,
    share_token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    uid TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    start_local TEXT NOT NULL,
    end_local TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    url TEXT,
    organizer TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_building ON events(building_id, start_local);
"""

EVENT_FIELDS = ("title", "description", "location", "start_local", "end_local", "all_day", "url", "organizer")

Conn = sqlite3.Connection


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> Conn:
    # FastAPI may run a dependency and its endpoint on different threadpool threads.
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = connect()
    con.executescript(SCHEMA)
    con.close()


# --- users ---

def create_user(con: Conn, email, password_hash):
    cur = con.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email, password_hash, now_iso()),
    )
    con.commit()
    return cur.lastrowid


def get_user_by_email(con: Conn, email):
    return con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


# --- buildings ---

def list_buildings(con: Conn, owner_id):
    return con.execute(
        """SELECT b.*, (SELECT COUNT(*) FROM events e WHERE e.building_id = b.id) AS event_count
           FROM buildings b WHERE owner_id = ? ORDER BY name""",
        (owner_id,),
    ).fetchall()


def get_building(con: Conn, building_id, owner_id):
    return con.execute(
        "SELECT * FROM buildings WHERE id = ? AND owner_id = ?", (building_id, owner_id)
    ).fetchone()


def get_building_by_token(con: Conn, token):
    return con.execute("SELECT * FROM buildings WHERE share_token = ?", (token,)).fetchone()


def create_building(con: Conn, owner_id, name, address, tz):
    cur = con.execute(
        "INSERT INTO buildings (owner_id, name, address, timezone, share_token, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner_id, name, address, tz, secrets.token_urlsafe(9), now_iso()),
    )
    con.commit()
    return cur.lastrowid


def update_building(con: Conn, building_id, name, address, tz):
    con.execute(
        "UPDATE buildings SET name = ?, address = ?, timezone = ? WHERE id = ?",
        (name, address, tz, building_id),
    )
    con.commit()


def regenerate_token(con: Conn, building_id):
    con.execute("UPDATE buildings SET share_token = ? WHERE id = ?", (secrets.token_urlsafe(9), building_id))
    con.commit()


# --- events ---

def list_events(con: Conn, building_id):
    return con.execute(
        "SELECT * FROM events WHERE building_id = ? ORDER BY start_local", (building_id,)
    ).fetchall()


def get_event(con: Conn, event_id, owner_id):
    return con.execute(
        """SELECT e.* FROM events e JOIN buildings b ON b.id = e.building_id
           WHERE e.id = ? AND b.owner_id = ?""",
        (event_id, owner_id),
    ).fetchone()


def create_event(con: Conn, building_id, data):
    ts = now_iso()
    cur = con.execute(
        f"""INSERT INTO events (building_id, uid, {", ".join(EVENT_FIELDS)}, created_at, updated_at)
            VALUES (?, ?, {", ".join("?" for _ in EVENT_FIELDS)}, ?, ?)""",
        (building_id, f"{uuid.uuid4()}@building-events", *(data[f] for f in EVENT_FIELDS), ts, ts),
    )
    con.commit()
    return cur.lastrowid


def update_event(con: Conn, event_id, data):
    con.execute(
        f"""UPDATE events SET {", ".join(f"{f} = ?" for f in EVENT_FIELDS)}, updated_at = ?
            WHERE id = ?""",
        (*(data[f] for f in EVENT_FIELDS), now_iso(), event_id),
    )
    con.commit()


def delete_event(con: Conn, event_id):
    con.execute("DELETE FROM events WHERE id = ?", (event_id,))
    con.commit()
