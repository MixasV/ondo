import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
import json


class CacheDB:
    """SQLite cache layer for dashboard data"""
    
    def __init__(self, db_path: str = "data/cache.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def init_db(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT,
                    url TEXT,
                    published_at TIMESTAMP,
                    tags TEXT,
                    lat REAL,
                    lon REAL,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            
            await db.commit()
    
    async def get_metric(self, key: str, max_age_minutes: int = 30) -> Optional[Any]:
        """Get cached metric if not expired"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT value, updated_at FROM metrics WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            updated_at = datetime.fromisoformat(row["updated_at"])
            if datetime.now() - updated_at > timedelta(minutes=max_age_minutes):
                return None
            
            return json.loads(row["value"])
    
    async def get_metric_timestamp(self, key: str) -> Optional[datetime]:
        """Get timestamp of when metric was last updated"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT updated_at FROM metrics WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return datetime.fromisoformat(row["updated_at"])
    
    async def set_update_progress(self, current: int, total: int, stage: str):
        """Store update progress"""
        await self.set_metric("update_progress", {
            "current": current,
            "total": total,
            "stage": stage,
            "timestamp": datetime.now().isoformat()
        })
    
    async def get_update_progress(self) -> Optional[dict]:
        """Get current update progress"""
        return await self.get_metric("update_progress", max_age_minutes=5)
    
    async def set_metric(self, key: str, value: Any):
        """Store metric in cache"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO metrics (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), datetime.now().isoformat())
            )
            await db.commit()
    
    async def get_recent_events(self, hours: int = 24, limit: int = 20) -> list[dict]:
        """Get recent events from cache"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cutoff = datetime.now() - timedelta(hours=hours)
            
            cursor = await db.execute(
                """SELECT * FROM events 
                   WHERE created_at > ? 
                   ORDER BY published_at DESC 
                   LIMIT ?""",
                (cutoff.isoformat(), limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_event(self, event: dict):
        """Add event to cache"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO events 
                   (id, title, source, url, published_at, tags, lat, lon, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["id"],
                    event["title"],
                    event.get("source"),
                    event.get("url"),
                    event.get("published_at"),
                    json.dumps(event.get("tags", [])),
                    event.get("lat"),
                    event.get("lon"),
                    datetime.now().isoformat()
                )
            )
            await db.commit()


cache = CacheDB()
