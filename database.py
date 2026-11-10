"""Ma'lumotlar bazasi (SQLite) — foydalanuvchilar, videolar, sozlamalar."""
import aiosqlite
from datetime import datetime, timezone

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TEXT,
                last_active TEXT,
                is_blocked INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                file_unique_id TEXT,
                caption TEXT,
                duration INTEGER,
                file_size INTEGER,
                created_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- Foydalanuvchilar ----------
async def upsert_user(user_id: int, username: str | None, full_name: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, joined_at, last_active, is_blocked)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_active=excluded.last_active,
                is_blocked=0
        """, (user_id, username, full_name, _now(), _now()))
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY joined_at ASC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def set_blocked(user_id: int, blocked: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=? WHERE user_id=?",
                         (1 if blocked else 0, user_id))
        await db.commit()


# ---------- Videolar (ombor) ----------
async def add_video(file_id: str, file_unique_id: str | None, caption: str | None,
                    duration: int | None, file_size: int | None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO videos (file_id, file_unique_id, caption, duration, file_size, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (file_id, file_unique_id, caption, duration, file_size, _now()))
        await db.commit()
        return cur.lastrowid


async def get_videos_page(offset: int, limit: int):
    """Eng avval yuborilgani eng tepada (id ASC) — talab bo'yicha."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM videos WHERE is_active=1 ORDER BY id ASC LIMIT ? OFFSET ?
        """, (limit, offset)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_video_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM videos WHERE is_active=1") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_video_by_id(video_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM videos WHERE id=?", (video_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_videos():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM videos WHERE is_active=1 ORDER BY id ASC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_video(video_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE videos SET is_active=0 WHERE id=?", (video_id,))
        await db.commit()


async def update_caption(video_id: int, caption: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE videos SET caption=? WHERE id=?", (caption, video_id))
        await db.commit()


# ---------- Sozlamalar ----------
async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        await db.commit()


async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def delete_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM settings WHERE key=?", (key,))
        await db.commit()
