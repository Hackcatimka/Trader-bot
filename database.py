from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH

_ALLOWED_FIELDS = frozenset(
    {"timeframe", "threshold", "volume_threshold", "min_volume_usd", "active"}
)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id          INTEGER PRIMARY KEY,
                timeframe        INTEGER NOT NULL DEFAULT 15,
                threshold        REAL    NOT NULL DEFAULT 10.0,
                volume_threshold REAL    NOT NULL DEFAULT 50.0,
                min_volume_usd   REAL    NOT NULL DEFAULT 1000000.0,
                active           INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id     INTEGER NOT NULL,
                symbol      TEXT    NOT NULL,
                last_signal TEXT    NOT NULL,
                PRIMARY KEY (user_id, symbol)
            )
        """)
        await db.commit()


async def ensure_user(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row)


async def update_user(user_id: int, **kwargs) -> None:
    if not kwargs:
        return
    unknown = set(kwargs.keys()) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = [*kwargs.values(), user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE user_id = ?", vals)
        await db.commit()


async def get_all_active_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE active = 1") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def load_cooldowns() -> dict[tuple[int, str], float]:
    """Load persisted cooldowns from DB into memory at startup."""
    result: dict[tuple[int, str], float] = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, symbol, last_signal FROM cooldowns"
        ) as cur:
            rows = await cur.fetchall()
    for user_id, symbol, last_signal_str in rows:
        try:
            dt = datetime.fromisoformat(last_signal_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            result[(int(user_id), symbol)] = dt.timestamp()
        except Exception:
            pass
    return result


async def save_cooldown(user_id: int, symbol: str, ts: float) -> None:
    dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO cooldowns (user_id, symbol, last_signal)
               VALUES (?, ?, ?)""",
            (user_id, symbol, dt_str),
        )
        await db.commit()
