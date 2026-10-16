"""Read-only reconciliation for unified parts. Never prints connection settings."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.database import engine

QUERIES = {
    "migration": "SELECT version_num FROM alembic_version",
    "parts": """SELECT count(*) total,
      count(*) FILTER(WHERE customer_id IS NULL) no_customer,
      count(*) FILTER(WHERE NULLIF(btrim(internal_part_no),'') IS NULL) no_internal,
      count(*) FILTER(WHERE NULLIF(btrim(customer_part_no),'') IS NULL) no_customer_no,
      count(*) FILTER(WHERE parent_part_id IS NOT NULL) derived,
      count(*) FILTER(WHERE process_type IS NOT NULL) with_process FROM parts""",
    "single_alias_match": """WITH a AS (
      SELECT part_id,min(customer_id) customer_id,min(customer_part_no) customer_part_no,
      min(customer_part_name) customer_part_name FROM part_customer_aliases
      WHERE is_active GROUP BY part_id HAVING count(*)=1)
      SELECT count(*) total, count(*) FILTER(WHERE p.customer_id IS DISTINCT FROM a.customer_id
      OR p.customer_part_no IS DISTINCT FROM a.customer_part_no
      OR p.customer_part_name IS DISTINCT FROM a.customer_part_name) mismatches
      FROM a JOIN parts p ON p.id=a.part_id""",
    "alias_groups": """SELECT count(*) multiple_alias_parts,
      count(*) FILTER(WHERE customers>1) multiple_customer_parts
      FROM (SELECT part_id,count(DISTINCT customer_id) customers
      FROM part_customer_aliases WHERE is_active GROUP BY part_id HAVING count(*)>1) a""",
    "duplicate_customer_numbers_without_revision": """SELECT count(*) groups,coalesce(sum(n),0) rows
      FROM (SELECT count(*) n FROM parts WHERE customer_id IS NOT NULL
      AND NULLIF(btrim(customer_part_no),'') IS NOT NULL
      GROUP BY customer_id,customer_part_no HAVING count(*)>1) a""",
    "legacy_alias_revisions": """SELECT count(*) total,
      count(*) FILTER(WHERE NULLIF(btrim(revision),'') IS NOT NULL) populated,
      count(DISTINCT revision) distinct_versions FROM part_customer_aliases WHERE is_active""",
    "gaibo_counts": """SELECT (SELECT count(*) FROM gaibo_single_parts) single_parts,
      (SELECT count(*) FROM gaibo_customer_requirements) requirements,
      (SELECT count(*) FROM gaibo_installation_packages) packages,
      (SELECT count(*) FROM gaibo_package_items) items,
      (SELECT count(*) FROM "part_BOM") bom""",
    "gaibo_links": """SELECT count(*) FILTER(WHERE g.part_id IS NULL) unlinked,
      count(*) FILTER(WHERE p.id IS NOT NULL) linked,
      count(*) FILTER(WHERE g.part_id IS NOT NULL AND p.id IS NULL) dangling,
      count(*) FILTER(WHERE NULLIF(btrim(g.tianyue_internal_part_no),'') IS NOT NULL) with_internal_number
      FROM gaibo_single_parts g LEFT JOIN parts p ON p.id=g.part_id""",
    "gaibo_single_part_mapping_preview": """WITH exact_candidates AS (
      SELECT g.id legacy_single_part_id, count(p.id) candidate_count
      FROM gaibo_single_parts g
      LEFT JOIN parts p ON NULLIF(btrim(g.tianyue_internal_part_no),'') IS NOT NULL
        AND lower(btrim(p.internal_part_no))=lower(btrim(g.tianyue_internal_part_no))
        AND p.is_deleted IS FALSE
      WHERE g.part_id IS NULL
      GROUP BY g.id
    ), linked_targets AS (
      SELECT part_id, count(*) n FROM gaibo_single_parts
      WHERE part_id IS NOT NULL GROUP BY part_id
    )
      SELECT
        (SELECT count(*) FROM gaibo_single_parts WHERE part_id IS NULL) unlinked_legacy_rows,
        (SELECT count(*) FROM exact_candidates WHERE candidate_count=1) unique_internal_number_candidate,
        (SELECT count(*) FROM exact_candidates WHERE candidate_count>1) ambiguous_internal_number_candidate,
        (SELECT count(*) FROM exact_candidates WHERE candidate_count=0) no_internal_number_candidate,
        (SELECT count(*) FROM linked_targets WHERE n>1) multiple_legacy_rows_per_part
    """,
    "gaibo_requirement_links": """SELECT count(*) total,
      count(*) FILTER(WHERE p.id IS NOT NULL) linked_to_parts,
      count(*) FILTER(WHERE g.id IS NULL) missing_single,
      count(*) FILTER(WHERE w.after_sales_customer_id IS NULL) missing_customer
      FROM gaibo_customer_requirements r LEFT JOIN gaibo_single_parts g ON g.id=r.single_part_id
      LEFT JOIN parts p ON p.id=g.part_id LEFT JOIN gaibo_customer_workspaces w ON w.id=r.workspace_id""",
    "package_item_states": "SELECT match_state,count(*) n FROM gaibo_package_items GROUP BY match_state ORDER BY match_state",
    "workspace_customer_schema": """SELECT column_name FROM information_schema.columns
      WHERE table_name='gaibo_customer_workspaces' AND column_name LIKE '%customer%'""",
    "customers": """SELECT (SELECT count(*) FROM customers) main_customers,
      (SELECT count(*) FROM gaibo_after_sales_customers) after_sales_customers,
      (SELECT count(*) FROM gaibo_customer_workspaces) workspaces""",
    "after_sales_customer_exact_candidates": """SELECT g.name,
      count(c.id) exact_name_matches FROM gaibo_after_sales_customers g
      LEFT JOIN customers c ON lower(btrim(c.name))=lower(btrim(g.name))
      GROUP BY g.id,g.name""",
    "after_sales_customer_mapping_preview": """WITH candidates AS (
      SELECT g.id, count(c.id) candidate_count
      FROM gaibo_after_sales_customers g
      LEFT JOIN customers c ON lower(btrim(c.name))=lower(btrim(g.name))
      GROUP BY g.id
    ) SELECT
      (SELECT count(*) FROM gaibo_after_sales_customers) legacy_after_sales_customers,
      count(*) FILTER(WHERE candidate_count=1) unique_exact_name_candidate,
      count(*) FILTER(WHERE candidate_count>1) ambiguous_exact_name_candidate,
      count(*) FILTER(WHERE candidate_count=0) no_exact_name_candidate
      FROM candidates""",
    "legacy_revision_values": "SELECT revision,count(*) n FROM part_customer_aliases WHERE is_active GROUP BY revision ORDER BY revision",
    "single_alias_quality": """SELECT a.data_quality_status,count(*) n
      FROM part_customer_aliases a JOIN (SELECT part_id FROM part_customer_aliases
      WHERE is_active GROUP BY part_id HAVING count(*)=1) s ON s.part_id=a.part_id
      WHERE a.is_active GROUP BY a.data_quality_status ORDER BY a.data_quality_status""",
    "duplicate_customer_numbers_with_alias_revision": """SELECT count(*) groups,coalesce(sum(n),0) rows FROM (
      SELECT customer_id,customer_part_no,revision,count(DISTINCT part_id) n
      FROM part_customer_aliases WHERE is_active AND customer_id IS NOT NULL
      AND NULLIF(btrim(customer_part_no),'') IS NOT NULL GROUP BY 1,2,3
      HAVING count(DISTINCT part_id)>1) a""",
    "parts_version_values": "SELECT version,count(*) n FROM parts GROUP BY version ORDER BY version",
    "package_item_links": """SELECT count(*) FILTER(WHERE r.id IS NOT NULL) linked_requirement,
      count(*) FILTER(WHERE p.id IS NOT NULL) linked_part,
      count(*) FILTER(WHERE i.quantity<=0) invalid_quantity
      FROM gaibo_package_items i LEFT JOIN gaibo_customer_requirements r ON r.id=i.requirement_id
      LEFT JOIN gaibo_single_parts g ON g.id=r.single_part_id LEFT JOIN parts p ON p.id=g.part_id""",
    "package_item_mapping_preview": """SELECT
      count(*) total_items,
      count(*) FILTER(WHERE i.requirement_id IS NOT NULL) linked_to_legacy_requirement,
      count(*) FILTER(WHERE i.requirement_id IS NULL) without_legacy_requirement,
      count(*) FILTER(WHERE i.match_state IN ('unlinked','missing_ibi')) unresolved_state,
      count(*) FILTER(WHERE NULLIF(btrim(i.tianyue_internal_composition),'') IS NULL) missing_internal_composition,
      count(*) FILTER(WHERE i.quantity<=0) invalid_quantity
      FROM gaibo_package_items i""",
    "package_component_identity_candidates": """WITH candidates AS (
      SELECT i.id package_item_id, count(DISTINCT a.part_id) candidate_parts
      FROM gaibo_package_items i
      JOIN gaibo_installation_packages pk ON pk.id=i.package_id
      JOIN gaibo_customer_workspaces w ON w.id=pk.workspace_id
      JOIN gaibo_after_sales_customers ac ON ac.id=w.after_sales_customer_id
      JOIN customers c ON lower(btrim(c.name))=lower(btrim(ac.name))
      LEFT JOIN part_customer_aliases a ON a.customer_id=c.id
        AND a.is_active IS TRUE
        AND a.data_quality_status='approved'
        AND lower(btrim(a.customer_part_no))=lower(btrim(i.unlinked_customer_part_number))
      WHERE NULLIF(btrim(i.unlinked_customer_part_number),'') IS NOT NULL
      GROUP BY i.id
    ) SELECT
      count(*) total_with_customer_part_number,
      count(*) FILTER(WHERE candidate_parts=1) unique_approved_alias_candidate,
      count(*) FILTER(WHERE candidate_parts>1) ambiguous_approved_alias_candidate,
      count(*) FILTER(WHERE candidate_parts=0) no_approved_alias_candidate
      FROM candidates""",
}

async def main():
    engine.echo = False
    failures = 0
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            for name, query in QUERIES.items():
                try:
                    async with conn.begin_nested():
                        rows = (await conn.execute(text(query))).mappings().all()
                        print(json.dumps({name: [dict(row) for row in rows]}, ensure_ascii=True, default=str))
                except Exception as exc:
                    failures += 1
                    print(json.dumps({name: {"error_type": type(exc).__name__}}))
            await conn.rollback()
    finally:
        await engine.dispose()
    return bool(failures)

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
