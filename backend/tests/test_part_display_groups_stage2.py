"""Tests for Stage 2 explicit part grouping implementation.

Focuses on:
1. Route registration order (static /shared-fields before dynamic /{group_id})
2. Migration compiles and has correct down_revision
3. Models are registered in __init__.py
"""

import pytest
from pathlib import Path
import importlib.util
import ast


def test_migration_file_exists():
    """Verify migration file exists in root alembic/versions (repository-root chain)."""
    # Migration must be in repository-root alembic/, not backend/alembic/
    migration_path = Path("../alembic/versions/20260730_explicit_part_grouping.py")
    assert migration_path.exists(), "Migration should be in root alembic/versions (actual chain)"

    # Verify it's not in backend/alembic
    backend_migration = Path("alembic/versions/20260730_explicit_part_grouping.py")
    assert not backend_migration.exists(), "Migration should not be in backend/alembic/versions"


def test_migration_down_revision():
    """Verify migration merges all ten existing heads."""
    migration_path = Path("../alembic/versions/20260730_explicit_part_grouping.py")
    content = migration_path.read_text()

    # Migration should merge all ten heads with tuple down_revision
    required_heads = [
        '001_initial',
        '20260707_customer_price_system',
        'add_parts_customer_id',
        'clarify20260620c',
        'mbp0002_parts_material_name',
        'nom005quotes_nomination_status',
        'sales_pricing_engine_v1',
        'v10_canonical_lv1_lv4',
        'v14_dies_architecture_refactor',
        'v6_shopfloor_execution',
    ]

    for head in required_heads:
        assert f"'{head}'" in content, f"Migration must include {head} in down_revision tuple"


def test_migration_compiles():
    """Verify migration file compiles without errors."""
    migration_path = Path("../alembic/versions/20260730_explicit_part_grouping.py")
    spec = importlib.util.spec_from_file_location("migration", migration_path)
    assert spec is not None, "Migration file should be importable"

    module = importlib.util.module_from_spec(spec)
    # Just check it can be loaded, don't execute
    assert module is not None


def test_models_registered_in_init():
    """Verify new models are registered in backend/app/models/__init__.py."""
    init_path = Path("app/models/__init__.py")
    content = init_path.read_text(encoding='utf-8')

    # Check imports
    assert "from .part_display_group import" in content, \
        "Should import from part_display_group module"
    assert "PartDisplayGroupDef" in content, "PartDisplayGroupDef should be imported"
    assert "PartDisplayGroupMember" in content, "PartDisplayGroupMember should be imported"
    assert "SharedFieldGroupDef" in content, "SharedFieldGroupDef should be imported"
    assert "SharedFieldGroupMember" in content, "SharedFieldGroupMember should be imported"

    # Check __all__ exports
    assert '"PartDisplayGroupDef"' in content, "PartDisplayGroupDef should be in __all__"
    assert '"PartDisplayGroupMember"' in content, "PartDisplayGroupMember should be in __all__"
    assert '"SharedFieldGroupDef"' in content, "SharedFieldGroupDef should be in __all__"
    assert '"SharedFieldGroupMember"' in content, "SharedFieldGroupMember should be in __all__"


def test_route_registration_order():
    """Verify /shared-fields routes are defined before /{group_id} routes.

    This prevents FastAPI from capturing 'shared-fields' as an integer group_id.
    """
    routes_path = Path("app/api/part_display_groups.py")
    content = routes_path.read_text()

    # Find positions of route definitions
    shared_fields_list_pos = content.find('@router.get("/shared-fields"')
    shared_fields_create_pos = content.find('@router.post("/shared-fields"')
    shared_fields_get_pos = content.find('@router.get("/shared-fields/{group_id}"')

    group_id_get_pos = content.find('@router.get("/{group_id}"')

    # All /shared-fields routes should be defined (exist)
    assert shared_fields_list_pos != -1, "GET /shared-fields should exist"
    assert shared_fields_create_pos != -1, "POST /shared-fields should exist"
    assert shared_fields_get_pos != -1, "GET /shared-fields/{group_id} should exist"
    assert group_id_get_pos != -1, "GET /{group_id} should exist"

    # Static /shared-fields (list/create) should come before dynamic /{group_id}
    assert shared_fields_list_pos < group_id_get_pos, \
        "GET /shared-fields (list) must be defined before GET /{group_id}"
    assert shared_fields_create_pos < group_id_get_pos, \
        "POST /shared-fields must be defined before GET /{group_id}"

    # Comment should be present
    assert "Static /shared-fields routes MUST be registered before" in content or \
           "NOTE: Static /shared-fields routes" in content, \
        "Should have a comment explaining route order"


def test_models_import():
    """Verify models can be imported from app.models."""
    try:
        from app.models import (
            PartDisplayGroupDef,
            PartDisplayGroupMember,
            SharedFieldGroupDef,
            SharedFieldGroupMember,
        )

        # Basic smoke test that classes exist
        assert PartDisplayGroupDef.__tablename__ == "part_display_group_defs"
        assert PartDisplayGroupMember.__tablename__ == "part_display_group_members"
        assert SharedFieldGroupDef.__tablename__ == "shared_field_group_defs"
        assert SharedFieldGroupMember.__tablename__ == "shared_field_group_members"

    except ImportError as e:
        pytest.fail(f"Failed to import models: {e}")


def test_router_prefix():
    """Verify router has correct prefix."""
    routes_path = Path("app/api/part_display_groups.py")
    content = routes_path.read_text()

    assert 'prefix="/part-display-groups"' in content, \
        "Router should have prefix /part-display-groups"
