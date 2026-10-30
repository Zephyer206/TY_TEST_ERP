"""Run with python -m app.workers.qr_notifications after authenticated deployment."""
import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.notification_service import backfill_recipients, dispatch_due


async def tick(sessions):
    async with sessions() as db:
        try:
            backfilled = await backfill_recipients(db)
            summary = await dispatch_due(db)
            await db.commit()
            return {**summary, "groups_checked": backfilled}
        except BaseException:
            await db.rollback()
            raise


async def run(sessions, stop, *, interval=15):
    while not stop.is_set():
        try:
            await tick(sessions)
        except asyncio.CancelledError:
            raise
        except Exception:
            # No SQL, exception text, connection URLs or payloads in worker logs.
            print("QR_NOTIFICATION_TICK_FAILED", flush=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


async def main(once, interval):
    if settings.AUTH_DISABLED:
        raise RuntimeError("AUTHENTICATION_REQUIRED")
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True,
        connect_args={"timeout": 10, "command_timeout": 30})
    try:
        async with engine.connect() as db:
            for name in ("notification_outbox", "qr_notifications", "qr_notification_attempts", "exception_recipient_groups"):
                if await db.scalar(text("SELECT to_regclass(:name)"), {"name": name}) is None:
                    raise RuntimeError("QR_SCHEMA_REQUIRED")
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        if once:
            print(json.dumps(await tick(sessions)))
        else:
            await run(sessions, asyncio.Event(), interval=interval)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, choices=range(1, 31), default=15)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.once, args.interval_seconds))
    except KeyboardInterrupt:
        pass
    except Exception:
        print("QR_NOTIFICATION_WORKER_UNAVAILABLE", flush=True)
        raise SystemExit(1)
