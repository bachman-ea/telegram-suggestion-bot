import asyncio
import sqlite3
import threading
from typing import Any


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    user_username TEXT,
                    user_message_id INTEGER NOT NULL,
                    user_status_message_id INTEGER,
                    post_type TEXT NOT NULL,
                    text TEXT,
                    media_data TEXT,
                    admin_chat_id INTEGER,
                    admin_message_id INTEGER,
                    moderator_id INTEGER,
                    moderator_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    scheduled_at TEXT,
                    published_at TEXT,
                    author_notified_accepted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status_sched ON posts(status, scheduled_at)")

            try:
                self.conn.execute("ALTER TABLE posts ADD COLUMN user_status_message_id INTEGER")
            except sqlite3.OperationalError:
                pass

            try:
                self.conn.execute("ALTER TABLE posts ADD COLUMN revision_comment TEXT")
            except sqlite3.OperationalError:
                pass

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    user_username TEXT,
                    reason TEXT NOT NULL,
                    banned_by_id INTEGER NOT NULL,
                    banned_by_name TEXT NOT NULL,
                    banned_at TEXT NOT NULL
                )
            """)
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    async def add_post(
        self,
        user_id: int,
        user_name: str,
        user_username: str | None,
        user_message_id: int,
        post_type: str,
        text: str | None,
        media_data: str | None,
        created_at: str,
    ) -> int:
        def _query() -> int:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO posts (
                        user_id, user_name, user_username, user_message_id,
                        post_type, text, media_data, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (
                    user_id,
                    user_name,
                    user_username,
                    user_message_id,
                    post_type,
                    text,
                    media_data,
                    created_at,
                ))
                self.conn.commit()
                return cursor.lastrowid

        return await asyncio.to_thread(_query)

    async def get_post(self, post_id: int) -> dict[str, Any] | None:
        def _query() -> dict[str, Any] | None:
            with self.lock:
                row = self.conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_query)

    async def update_admin_message(self, post_id: int, admin_chat_id: int | str, admin_message_id: int) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    UPDATE posts 
                    SET admin_chat_id = ?, admin_message_id = ?
                    WHERE id = ?
                """, (admin_chat_id, admin_message_id, post_id))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def update_user_status_message(self, post_id: int, user_status_message_id: int) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    UPDATE posts 
                    SET user_status_message_id = ?
                    WHERE id = ?
                """, (user_status_message_id, post_id))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def mark_author_notified(self, post_id: int) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    UPDATE posts 
                    SET author_notified_accepted = 1
                    WHERE id = ?
                """, (post_id,))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def set_status(
        self,
        post_id: int,
        status: str,
        moderator_id: int | None = None,
        moderator_name: str | None = None,
        scheduled_at: str | None = None,
        published_at: str | None = None,
        revision_comment: str | None = None,
    ) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    UPDATE posts
                    SET status = ?,
                        moderator_id = COALESCE(?, moderator_id),
                        moderator_name = COALESCE(?, moderator_name),
                        scheduled_at = CASE WHEN ? IS NOT NULL THEN ? ELSE scheduled_at END,
                        published_at = CASE WHEN ? IS NOT NULL THEN ? ELSE published_at END,
                        revision_comment = CASE WHEN ? IS NOT NULL THEN ? ELSE revision_comment END
                    WHERE id = ?
                """, (
                    status,
                    moderator_id,
                    moderator_name,
                    scheduled_at,
                    scheduled_at,
                    published_at,
                    published_at,
                    revision_comment,
                    revision_comment,
                    post_id,
                ))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def cancel_scheduled_post(self, post_id: int) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    UPDATE posts
                    SET status = 'approved',
                        scheduled_at = NULL
                    WHERE id = ?
                """, (post_id,))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def get_scheduled_posts(self) -> list[dict[str, Any]]:
        def _query() -> list[dict[str, Any]]:
            with self.lock:
                rows = self.conn.execute("""
                    SELECT * FROM posts 
                    WHERE status = 'scheduled' AND scheduled_at IS NOT NULL
                    ORDER BY scheduled_at ASC
                """).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_query)

    async def get_stats(self) -> dict[str, int]:
        def _query() -> dict[str, int]:
            with self.lock:
                rows = self.conn.execute("""
                    SELECT status, COUNT(*) as cnt FROM posts GROUP BY status
                """).fetchall()
                stats = {"pending": 0, "approved": 0, "scheduled": 0, "published": 0, "rejected": 0, "needs_revision": 0}
                for r in rows:
                    if r["status"] in stats:
                        stats[r["status"]] = r["cnt"]
                return stats

        return await asyncio.to_thread(_query)

    async def ban_user(
        self,
        user_id: int,
        user_name: str,
        user_username: str | None,
        reason: str,
        banned_by_id: int,
        banned_by_name: str,
        banned_at: str,
    ) -> None:
        def _query() -> None:
            with self.lock:
                self.conn.execute("""
                    INSERT OR REPLACE INTO banned_users (
                        user_id, user_name, user_username, reason,
                        banned_by_id, banned_by_name, banned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    user_name,
                    user_username,
                    reason,
                    banned_by_id,
                    banned_by_name,
                    banned_at,
                ))
                self.conn.commit()

        await asyncio.to_thread(_query)

    async def unban_user(self, user_id: int) -> bool:
        def _query() -> bool:
            with self.lock:
                cursor = self.conn.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
                self.conn.commit()
                return cursor.rowcount > 0

        return await asyncio.to_thread(_query)

    async def is_user_banned(self, user_id: int) -> dict[str, Any] | None:
        def _query() -> dict[str, Any] | None:
            with self.lock:
                row = self.conn.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,)).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_query)

    async def get_banned_users(self) -> list[dict[str, Any]]:
        def _query() -> list[dict[str, Any]]:
            with self.lock:
                rows = self.conn.execute("SELECT * FROM banned_users ORDER BY banned_at DESC").fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_query)
