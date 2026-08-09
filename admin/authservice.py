import aiosqlite
import bcrypt

class AdminAuthManager:
    """
    SQLite-backed admin credentials with forced password change on first login,
    similar to RabbitMQ's default guest/guest -> must-change pattern.
    """

    def __init__(self, db_path: str = "admin.db"):
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_user (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    must_change_password INTEGER NOT NULL DEFAULT 1
                )
            """)
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM admin_user")
            (count,) = await cursor.fetchone()
            if count == 0:
                # Seed default admin/admin, forced change on first login
                default_hash = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
                await db.execute(
                    "INSERT INTO admin_user (id, username, password_hash, must_change_password) "
                    "VALUES (1, 'admin', ?, 1)",
                    (default_hash,)
                )
                await db.commit()

    async def verify(self, username: str, password: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT username, password_hash FROM admin_user WHERE id = 1"
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            stored_username, stored_hash = row
            if username != stored_username:
                return False
            return bcrypt.checkpw(password.encode(), stored_hash.encode())

    async def must_change_password(self) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT must_change_password FROM admin_user WHERE id = 1"
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

    async def change_password(self, new_username: str, new_password: str) -> None:
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                "UPDATE admin_user SET username = ?, password_hash = ?, must_change_password = 0 WHERE id = 1",
                (new_username, new_hash)
            )
            await db.commit()