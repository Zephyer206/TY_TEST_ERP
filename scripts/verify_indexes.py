#!/usr/bin/env python3
"""
Database index verification script.

Validates that critical indexes exist and analyzes query performance.
Run this after schema changes to ensure proper indexing.
"""

import argparse
import os
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


# Critical indexes that should exist
CRITICAL_INDEXES = {
    # quotes table indexes
    "idx_quotes_part_id": "quotes(part_id)",
    "idx_quotes_customer_id": "quotes(customer_id)",
    "idx_quotes_approval_status": "quotes(approval_status)",
    "idx_quotes_is_deleted": "quotes(is_deleted)",
    "idx_quotes_created_at": "quotes(created_at)",

    # parts table indexes
    "idx_parts_part_number": "parts(part_number)",
    "idx_parts_customer_id": "parts(customer_id)",
    "idx_parts_status": "parts(status)",
    "idx_parts_is_deleted": "parts(is_deleted)",

    # machines table indexes
    "idx_machines_status": "machines(status)",
    "idx_machines_press_tonnage": "machines(press_tonnage)",

    # production_plans table indexes
    "idx_plans_part_id": "production_plans(part_id)",
    "idx_plans_status": "production_plans(status)",
    "idx_plans_plan_date": "production_plans(plan_date)",

    # tooling_molds table indexes
    "idx_molds_customer_id": "tooling_molds(customer_id)",
    "idx_molds_mold_status": "tooling_molds(mold_status)",
    "idx_molds_mold_number": "tooling_molds(mold_number)",

    # users table indexes
    "idx_users_username": "users(username)",
    "idx_users_role_level": "users(role_level)",

    # prices table indexes
    "idx_prices_part_customer": "prices(part_id, customer_id)",
    "idx_prices_is_deleted": "prices(is_deleted)",

    # Soft delete indexes
    "idx_quotes_deleted": "quotes(is_deleted, deleted_at)",
    "idx_parts_deleted": "parts(is_deleted, deleted_at)",
    "idx_users_deleted": "users(is_deleted)",
}

# Query patterns that should use indexes (for EXPLAIN analysis)
CRITICAL_QUERIES = [
    {
        "name": "Get quotes by status",
        "query": "SELECT * FROM quotes WHERE approval_status = 'PENDING_BOSS' AND is_deleted = false LIMIT 20",
    },
    {
        "name": "Get parts by customer",
        "query": "SELECT * FROM parts WHERE customer_id = 1 AND is_deleted = false",
    },
    {
        "name": "Get machine by status",
        "query": "SELECT * FROM machines WHERE status = 'running'",
    },
    {
        "name": "Get plans by date range",
        "query": "SELECT * FROM production_plans WHERE plan_date BETWEEN '2024-01-01' AND '2024-12-31'",
    },
    {
        "name": "Get prices by part and customer",
        "query": "SELECT * FROM prices WHERE part_id = 1 AND customer_id = 1",
    },
]


async def verify_indexes(db_url: str) -> dict:
    """Verify that critical indexes exist."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(db_url, echo=False)

    async with AsyncSession(engine) as session:
        results = {}

        for index_name, table_col in CRITICAL_INDEXES.items():
            try:
                # Check if index exists
                result = await session.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_indexes
                            WHERE indexname = :index_name
                        ) as exists
                    """),
                    {"index_name": index_name}
                )
                row = result.fetchone()
                exists = row[0] if row else False

                results[index_name] = {
                    "table_column": table_col,
                    "exists": exists,
                    "status": "OK" if exists else "MISSING",
                }
            except Exception as e:
                results[index_name] = {
                    "table_column": table_col,
                    "exists": False,
                    "status": f"ERROR: {e}",
                }

    await engine.dispose()
    return results


async def analyze_query_performance(db_url: str) -> list:
    """Analyze query performance using EXPLAIN."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    engine = create_async_engine(db_url, echo=False)
    results = []

    async with AsyncSession(engine) as session:
        for q in CRITICAL_QUERIES:
            try:
                explain_result = await session.execute(
                    text(f"EXPLAIN (FORMAT JSON) {q['query']}")
                )
                plan = explain_result.fetchone()[0]

                # Check for sequential scans (bad for large tables)
                seq_scan = False
                for node in _flatten_plan(plan):
                    if node.get("Operation") == "Seq Scan":
                        seq_scan = True
                        break

                results.append({
                    "name": q["name"],
                    "query": q["query"],
                    "uses_seq_scan": seq_scan,
                    "plan": plan,
                })
            except Exception as e:
                results.append({
                    "name": q["name"],
                    "query": q["query"],
                    "error": str(e),
                })

    await engine.dispose()
    return results


def _flatten_plan(plan: dict) -> list:
    """Flatten nested plan nodes."""
    nodes = []
    if "Plan" in plan:
        nodes.append(plan["Plan"])
        if "Plans" in plan["Plan"]:
            for sub in plan["Plan"]["Plans"]:
                nodes.extend(_flatten_plan({"Plan": sub}))
    return nodes


async def create_missing_indexes(db_url: str, missing: list) -> int:
    """Create missing indexes."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    # Index creation SQL (simplified - real implementation would map to actual columns)
    INDEX_CREATION_MAP = {
        "idx_quotes_part_id": "CREATE INDEX IF NOT EXISTS idx_quotes_part_id ON quotes(part_id)",
        "idx_quotes_customer_id": "CREATE INDEX IF NOT EXISTS idx_quotes_customer_id ON quotes(customer_id)",
        "idx_quotes_approval_status": "CREATE INDEX IF NOT EXISTS idx_quotes_approval_status ON quotes(approval_status)",
        "idx_quotes_is_deleted": "CREATE INDEX IF NOT EXISTS idx_quotes_is_deleted ON quotes(is_deleted)",
        "idx_parts_part_number": "CREATE INDEX IF NOT EXISTS idx_parts_part_number ON parts(part_number)",
        "idx_parts_customer_id": "CREATE INDEX IF NOT EXISTS idx_parts_customer_id ON parts(customer_id)",
        "idx_machines_status": "CREATE INDEX IF NOT EXISTS idx_machines_status ON machines(status)",
    }

    engine = create_async_engine(db_url, echo=False)
    created = 0

    async with AsyncSession(engine) as session:
        for index_name in missing:
            sql = INDEX_CREATION_MAP.get(index_name)
            if sql:
                try:
                    await session.execute(text(sql))
                    await session.commit()
                    print(f"  Created: {index_name}")
                    created += 1
                except Exception as e:
                    print(f"  Failed to create {index_name}: {e}")

    await engine.dispose()
    return created


def print_results(index_results: dict, query_results: list):
    """Print verification results."""
    print("\n" + "=" * 60)
    print("DATABASE INDEX VERIFICATION REPORT")
    print("=" * 60)

    # Index status
    print("\n[INDEX STATUS]")
    print("-" * 60)

    missing = []
    for name, info in sorted(index_results.items()):
        status_icon = "✓" if info["exists"] else "✗"
        print(f"  {status_icon} {name:40} {info['status']:10} ({info['table_column']})")
        if not info["exists"]:
            missing.append(name)

    # Summary
    total = len(index_results)
    existing = total - len(missing)
    print(f"\n  Total indexes checked: {total}")
    print(f"  Existing: {existing}")
    print(f"  Missing: {len(missing)}")

    # Query performance
    print("\n[QUERY PERFORMANCE]")
    print("-" * 60)

    for q in query_results:
        if "error" in q:
            print(f"  ✗ {q['name']}: ERROR - {q['error']}")
        elif q["uses_seq_scan"]:
            print(f"  ⚠ {q['name']}: Uses Sequential Scan (consider index)")
        else:
            print(f"  ✓ {q['name']}: OK (uses index)")

    return missing


async def main():
    parser = argparse.ArgumentParser(description='数据库索引验证')
    parser.add_argument('--create', action='store_true', help='自动创建缺失的索引')
    parser.add_argument('--db-url', help='数据库连接 URL')

    args = parser.parse_args()

    # Get database URL
    db_url = args.db_url or os.getenv(
        'DATABASE_URL',
        'postgresql+asyncpg://postgres:postgres@localhost:5432/zephyr_erp'
    )

    print("数据库索引验证工具")
    print("=" * 60)
    print(f"数据库: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    # Verify indexes
    print("\n验证索引...")
    index_results = await verify_indexes(db_url)

    # Analyze queries
    print("分析查询性能...")
    query_results = await analyze_query_performance(db_url)

    # Print results
    missing = print_results(index_results, query_results)

    # Create missing indexes if requested
    if missing and args.create:
        print("\n" + "=" * 60)
        print("创建缺失的索引...")
        print("-" * 60)
        created = await create_missing_indexes(db_url, missing)
        print(f"\n成功创建 {created} 个索引")

    # Exit code
    if missing:
        print(f"\n⚠ 警告: {len(missing)} 个索引缺失")
        return 1
    else:
        print("\n✓ 所有关键索引已存在")
        return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
