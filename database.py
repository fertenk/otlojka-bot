import sqlite3
import json
from datetime import datetime

DB_PATH = "bot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            allowed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            platform TEXT,
            price TEXT,
            description TEXT,
            channel_id TEXT,
            message_id INTEGER,
            status TEXT DEFAULT 'active',
            auto_delete_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_name TEXT,
            added_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Default settings
    defaults = {
        "task_template": "НОВОЕ ЗАДАНИЕ!\n\n• Платформа: {platform}\n• Оплата: {price}\n• Описание: {description}\n\n𖥔 — · ──  ·  easy money  ·  ── · — 𖥔",
        "closed_template": "🔓Данное задание закончилось, дождитесь следующего, чтобы приступить к работе!\n\n𖥔 — · ──  ·  easy money  ·  ── · — 𖥔",
        "btn_post": "📝 Выложить задание",
        "btn_stats": "📊 Статистика",
        "btn_delete": "🗑 Удалить задание",
        "btn_yandex": "🗺 Яндекс Карты",
        "btn_2gis": "🗺 2ГИС",
        "btn_google": "🗺 Гугл Карты",
        "btn_avito": "🛍 Авито",
        "btn_other": "✏️ Другое",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()


# ── Users ──────────────────────────────────────────────

def upsert_user(user_id, username, first_name):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username or "", first_name or ""),
    )
    conn.execute(
        "UPDATE users SET username=?, first_name=? WHERE user_id=?",
        (username or "", first_name or "", user_id),
    )
    conn.commit()
    conn.close()


def is_allowed(user_id):
    conn = get_conn()
    row = conn.execute("SELECT allowed FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row and row["allowed"] == 1


def set_allowed(user_id, allowed: bool):
    conn = get_conn()
    conn.execute("UPDATE users SET allowed=? WHERE user_id=?", (1 if allowed else 0, user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_username(username):
    username = username.lstrip("@")
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_user_by_username(username):
    username = username.lstrip("@")
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, allowed) VALUES (?, ?, 1)",
        (0, username),
    )
    # if user already exists just allow
    conn.execute("UPDATE users SET allowed=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()


# ── Tasks ──────────────────────────────────────────────

def create_task(user_id, platform, price, description, channel_id, message_id, auto_delete_at=None):
    conn = get_conn()
    c = conn.execute(
        """INSERT INTO tasks (user_id, platform, price, description, channel_id, message_id, auto_delete_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, platform, price, description, channel_id, message_id, auto_delete_at),
    )
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_active_tasks(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND status='active' ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def close_task(task_id):
    conn = get_conn()
    conn.execute("UPDATE tasks SET status='closed' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def get_tasks_to_auto_delete():
    conn = get_conn()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status='active' AND auto_delete_at IS NOT NULL AND auto_delete_at <= ?",
        (now,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_tasks_admin():
    conn = get_conn()
    rows = conn.execute(
        "SELECT t.*, u.username FROM tasks t LEFT JOIN users u ON t.user_id=u.user_id ORDER BY t.created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Channels ───────────────────────────────────────────

def add_channel(channel_id, channel_name):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO channels (channel_id, channel_name) VALUES (?, ?)",
        (channel_id, channel_name),
    )
    conn.commit()
    conn.close()


def get_channels():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM channels ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_channel(channel_id):
    conn = get_conn()
    conn.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()


# ── Settings ───────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_conn()
    total_users = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    allowed_users = conn.execute("SELECT COUNT(*) as n FROM users WHERE allowed=1").fetchone()["n"]
    total_tasks = conn.execute("SELECT COUNT(*) as n FROM tasks").fetchone()["n"]
    active_tasks = conn.execute("SELECT COUNT(*) as n FROM tasks WHERE status='active'").fetchone()["n"]
    conn.close()
    return {
        "total_users": total_users,
        "allowed_users": allowed_users,
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
    }
