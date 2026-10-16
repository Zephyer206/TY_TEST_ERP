"""
Inspect cloud PostgreSQL schema and compare with data-model.md design.
Generates current-schema.md with actual database structure.
"""

import asyncio
import asyncpg
from datetime import datetime


async def inspect_schema():
    conn = await asyncpg.connect(
        host='124.222.29.229',
        port=5432,
        user='postgres',
        password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
        database='stamping_system'
    )

    try:
        print('Inspecting cloud database schema...')
        print('=' * 80)

        # Get all tables
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        table_list = [t['table_name'] for t in tables]
        print(f"\nTotal tables: {len(table_list)}\n")

        # Group tables by entity (heuristic based on name patterns)
        entity_groups = {
            'User & Auth': [],
            'Quote': [],
            'Part': [],
            'Tooling/Die': [],
            'Machine': [],
            'Sampling': [],
            'Production': [],
            'Process Flow': [],
            'Warehouse/Material': [],
            'Quality': [],
            'Packaging': [],
            'Coating': [],
            'Dictionary': [],
            'Audit & Logging': [],
            'Other': []
        }

        for table in table_list:
            if 'user' in table or 'department' in table or 'permission' in table or 'auth' in table:
                entity_groups['User & Auth'].append(table)
            elif 'quote' in table or 'customer' in table:
                entity_groups['Quote'].append(table)
            elif 'part' in table and 'dict' not in table:
                entity_groups['Part'].append(table)
            elif 'die' in table or 'tooling' in table or 'mold' in table:
                entity_groups['Tooling/Die'].append(table)
            elif 'machine' in table:
                entity_groups['Machine'].append(table)
            elif 'sampling' in table or 'sample' in table:
                entity_groups['Sampling'].append(table)
            elif 'production' in table or 'plan' in table or 'report' in table:
                entity_groups['Production'].append(table)
            elif 'process' in table or 'flow' in table or 'card' in table:
                entity_groups['Process Flow'].append(table)
            elif 'material' in table or 'batch' in table or 'supplier' in table or 'warehouse' in table:
                entity_groups['Warehouse/Material'].append(table)
            elif 'quality' in table or 'inspection' in table or 'qc' in table or 'oqc' in table or 'iqc' in table or 'qa' in table or 'patrol' in table:
                entity_groups['Quality'].append(table)
            elif 'packaging' in table or 'pack' in table:
                entity_groups['Packaging'].append(table)
            elif 'coating' in table or 'recipe' in table:
                entity_groups['Coating'].append(table)
            elif 'dict' in table or '_type' in table:
                entity_groups['Dictionary'].append(table)
            elif 'audit' in table or 'log' in table or 'scan' in table:
                entity_groups['Audit & Logging'].append(table)
            else:
                entity_groups['Other'].append(table)

        # Print grouped tables
        for group, tables in entity_groups.items():
            if tables:
                print(f"\n## {group} ({len(tables)} tables)")
                for table in sorted(tables):
                    print(f"   - {table}")

        print('\n' + '=' * 80)
        print('\nDetailed schema inspection...\n')

        # Collect detailed schema info
        schema_info = {}

        for table_name in table_list:
            # Get columns
            columns = await conn.fetch("""
                SELECT
                    column_name,
                    data_type,
                    character_maximum_length,
                    column_default,
                    is_nullable,
                    udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = $1
                ORDER BY ordinal_position
            """, table_name)

            # Get primary key
            pk = await conn.fetch("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass AND i.indisprimary
            """, table_name)

            # Get foreign keys
            fks = await conn.fetch("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = $1
            """, table_name)

            # Get indexes
            indexes = await conn.fetch("""
                SELECT
                    i.relname AS index_name,
                    a.attname AS column_name,
                    ix.indisunique AS is_unique
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE t.relname = $1
                  AND t.relkind = 'r'
                  AND i.relname NOT LIKE '%_pkey'
            """, table_name)

            schema_info[table_name] = {
                'columns': columns,
                'primary_keys': [row['attname'] for row in pk],
                'foreign_keys': fks,
                'indexes': indexes
            }

        # Generate current-schema.md
        md_content = generate_schema_markdown(schema_info, entity_groups, table_list)

        with open('current-schema.md', 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f'\n[OK] Generated current-schema.md')
        print(f'Location: {os.path.abspath("current-schema.md")}')

        # Compare with data-model.md design
        print('\n' + '=' * 80)
        print('\nComparison with data-model.md design:\n')

        designed_tables = {
            'users', 'special_permissions_dict', 'departments', 'admin_context_switches',
            'quotes', 'quote_items', 'surface_treatments', 'quote_tech_reviews', 'customers',
            'parts', 'part_name_dict', 'part_customer_aliases', 'price_accounts',
            'annual_price_records', 'price_adjustments',
            'toolings', 'tooling_parts', 'tooling_maintenance_logs',
            'machines', 'machine_status_logs',
            'sampling_tasks',
            'production_plans', 'plan_machine_assignments', 'production_reports', 'production_sessions',
            'process_flow_cards',
            'material_batches', 'material_batch_children', 'suppliers',
            'first_piece_inspections', 'oqc_inspections', 'qa_exemptions', 'patrol_inspections',
            'packaging_records',
            'coating_recipes', 'coating_records',
            'audit_logs', 'qr_scan_logs'
        }

        actual_tables = set(table_list)

        missing_in_cloud = designed_tables - actual_tables
        extra_in_cloud = actual_tables - designed_tables
        common_tables = designed_tables & actual_tables

        print(f"Designed tables: {len(designed_tables)}")
        print(f"Cloud tables: {len(actual_tables)}")
        print(f"Common tables: {len(common_tables)}")
        print(f"Missing in cloud: {len(missing_in_cloud)}")
        print(f"Extra in cloud: {len(extra_in_cloud)}")

        if missing_in_cloud:
            print(f"\n[-] Tables designed but NOT in cloud ({len(missing_in_cloud)}):")
            for table in sorted(missing_in_cloud):
                print(f"   - {table}")

        if extra_in_cloud:
            print(f"\n[+] Tables in cloud but NOT designed ({len(extra_in_cloud)}):")
            for table in sorted(extra_in_cloud):
                print(f"   - {table}")

        # Sample data check for key tables
        print('\n' + '=' * 80)
        print('\nSample data check:\n')

        key_tables = ['users', 'quotes', 'parts', 'customers']
        for table in key_tables:
            if table in actual_tables:
                count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
                print(f"   {table}: {count} rows")
            else:
                print(f"   {table}: NOT FOUND")

    except Exception as e:
        print(f'\n[ERROR] {e}')
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


def generate_schema_markdown(schema_info, entity_groups, table_list):
    """Generate markdown documentation of current schema."""

    md = f"""# Current Database Schema

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Database**: PostgreSQL (stamping_system)
**Total Tables**: {len(table_list)}

---

## Overview

This document describes the ACTUAL database schema currently deployed in the cloud PostgreSQL instance.

"""

    # Add entity groups
    for group, tables in entity_groups.items():
        if not tables:
            continue

        md += f"\n## {group}\n\n"

        for table_name in sorted(tables):
            if table_name not in schema_info:
                continue

            info = schema_info[table_name]
            md += f"\n### Table: `{table_name}`\n\n"

            # Primary keys
            if info['primary_keys']:
                md += f"**Primary Key**: {', '.join(info['primary_keys'])}\n\n"

            # Columns
            md += "| Column | Type | Nullable | Default |\n"
            md += "|--------|------|----------|----------|\n"

            for col in info['columns']:
                col_name = col['column_name']

                # Format data type
                if col['data_type'] == 'character varying':
                    col_type = f"VARCHAR({col['character_maximum_length']})"
                elif col['data_type'] == 'USER-DEFINED':
                    col_type = col['udt_name']
                else:
                    col_type = col['data_type'].upper()

                nullable = '✓' if col['is_nullable'] == 'YES' else '✗'
                default = col['column_default'] or '-'

                # Highlight primary keys
                if col_name in info['primary_keys']:
                    col_name = f"**{col_name}** [PK]"

                md += f"| {col_name} | {col_type} | {nullable} | {default} |\n"

            # Foreign keys
            if info['foreign_keys']:
                md += "\n**Foreign Keys**:\n\n"
                for fk in info['foreign_keys']:
                    md += f"- `{fk['column_name']}` → `{fk['foreign_table_name']}.{fk['foreign_column_name']}`\n"

            # Indexes
            if info['indexes']:
                md += "\n**Indexes**:\n\n"
                seen_indexes = set()
                for idx in info['indexes']:
                    idx_name = idx['index_name']
                    if idx_name not in seen_indexes:
                        unique = ' (UNIQUE)' if idx['is_unique'] else ''
                        md += f"- `{idx_name}`{unique}\n"
                        seen_indexes.add(idx_name)

            md += "\n---\n"

    return md


if __name__ == '__main__':
    import os
    asyncio.run(inspect_schema())
