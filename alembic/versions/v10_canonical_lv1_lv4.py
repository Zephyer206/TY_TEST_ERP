"""
Stage 2A: Canonical LV1-LV4 Permission System Migration
========================================================

Implements the canonical 4-level permission system from:
specs/001-erp-system-architecture/plan.md lines 198-202

Changes:
1. Normalize existing role_level values to canonical LV1-LV4:
   - LV1: Ordinary staff (operators, warehouse, QC, spray, maintenance)
   - LV2: Managers & business/technical staff (team leaders, technical, business, supervisors)
   - LV3: Boss (final approval, global visibility)
   - LV4: Super administrator (system management, context switching)

2. Add CHECK constraint to enforce role_level in range 1-4
3. Remove is_superadmin column (replaced by role_level=4)

Data normalization: ONLY username='admin' with role_level=10 maps to LV4.
All other users must already be in range 1-4, or migration fails.

Dependencies: v10_tech_qa_pipeline
Execute: alembic upgrade head
Rollback: alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v10_canonical_lv1_lv4'
down_revision = 'v10_tech_qa_pipeline'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Step 1: Verify ONLY admin can be mapped
    print("Verifying migration safety: only admin (username='admin', role_level=10) can be migrated...")
    result = conn.execute(sa.text("""
        SELECT id, username, role_level, dept, position
        FROM users
        WHERE (role_level IS NULL OR role_level < 1 OR role_level > 4)
          AND NOT (username = 'admin' AND role_level = 10)
    """))
    invalid_users = result.fetchall()

    if invalid_users:
        users_info = "\n".join([
            f"  - ID {u[0]}: username='{u[1]}' role_level={u[2]} dept={u[3]} position={u[4]}"
            for u in invalid_users
        ])
        raise ValueError(
            f"Migration BLOCKED: Found {len(invalid_users)} user(s) with invalid role_level.\n"
            f"Invalid users:\n{users_info}\n\n"
            "ONLY username='admin' with role_level=10 has a verified mapping to LV4.\n"
            "All other users must have role_level between 1-4 before migration.\n"
            "Fix these users manually or via a data correction script before running this migration."
        )

    # Step 2: Normalize ONLY the admin user (username='admin', role_level=10 → 4)
    print("Normalizing admin user: role_level 10 → 4...")
    result = conn.execute(sa.text("""
        UPDATE users
        SET role_level = 4
        WHERE username = 'admin' AND role_level = 10
    """))

    if result.rowcount > 0:
        print(f"  Migrated {result.rowcount} admin user(s) from level 10 to LV4")

    # Step 3: Ensure role_level is NOT NULL (default to 1 if somehow NULL after checks)
    print("Ensuring role_level is NOT NULL...")
    op.alter_column('users', 'role_level',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='1')

    # Step 4: Add CHECK constraint to enforce role_level 1-4
    print("Adding CHECK constraint for role_level 1-4...")
    op.create_check_constraint(
        'ck_users_role_level_1_4',
        'users',
        'role_level >= 1 AND role_level <= 4'
    )

    # Step 5: Remove is_superadmin column (replaced by role_level=4)
    print("Removing is_superadmin column if exists...")
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'is_superadmin' in columns:
        op.drop_column('users', 'is_superadmin')

    print("Migration complete: Canonical LV1-LV4 system activated")


def downgrade():
    """Downgrade not supported: LV1-LV4 is the canonical forward-only permission system.

    The legacy 10-level system with is_superadmin has been permanently retired.
    Rolling back would reintroduce inconsistent permission semantics that have been
    systematically removed from all runtime code, API endpoints, and frontend logic.

    If you need to undo this migration, restore from a database backup taken before
    the migration was applied.
    """
    raise NotImplementedError(
        "Downgrade from canonical LV1-LV4 is not supported. "
        "The legacy permission system has been fully removed from the codebase. "
        "Restore from backup if rollback is required."
    )
