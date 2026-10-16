"""Read-only database preflight; never print connection details or exceptions."""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def check():
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from app.core.config import settings, validate_runtime_settings
    from app.database import engine

    validate_runtime_settings()
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
        raise ValueError("Invalid database configuration")
    if "<" in settings.DATABASE_URL:
        raise ValueError("Replace database placeholders")
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(check(), timeout=20))
    except Exception as error:
        print(f"Database/configuration check failed ({type(error).__name__}). "
              "Check backend/.env and database connectivity. Connection details are hidden.")
        sys.exit(1)
    print("Database connection: PASS (SELECT 1 only; no schema/data changes).")
