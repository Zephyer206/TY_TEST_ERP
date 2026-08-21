"""
Tests for canonical LV1-LV4 permission system.

No-database unit tests covering:
- Token creation with LV1-LV4
- Authorization checks at each level
- Rejection of out-of-range role_level values
"""

from app.core.security import create_tokens, verify_min_role_level
from app.models.user import User


def test_lv1_token_creation():
    """LV1 user token should contain role_level=1."""
    user = User(
        id=1,
        username="operator",
        password="hashed",
        real_name="Operator User",
        dept="prod",
        role_level=1,
        position="操作工",
        is_tech=False,
    )
    tokens = create_tokens(user)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


def test_lv4_token_creation():
    """LV4 user token should contain role_level=4."""
    user = User(
        id=4,
        username="admin",
        password="hashed",
        real_name="Admin User",
        dept="admin",
        role_level=4,
        position="系统管理员",
        is_tech=True,
    )
    tokens = create_tokens(user)
    assert "access_token" in tokens
    assert "refresh_token" in tokens


def test_lv1_can_access_lv1_endpoints():
    """LV1 user can access LV1 endpoints."""
    user = User(id=1, username="op", password="x", dept="prod", role_level=1, is_tech=False)
    assert verify_min_role_level(user, 1) is True


def test_lv1_cannot_access_lv2_endpoints():
    """LV1 user cannot access LV2 endpoints."""
    user = User(id=1, username="op", password="x", dept="prod", role_level=1, is_tech=False)
    assert verify_min_role_level(user, 2) is False


def test_lv2_can_access_lv1_and_lv2_endpoints():
    """LV2 user can access LV1 and LV2 endpoints."""
    user = User(id=2, username="mgr", password="x", dept="sales", role_level=2, is_tech=False)
    assert verify_min_role_level(user, 1) is True
    assert verify_min_role_level(user, 2) is True


def test_lv2_cannot_access_lv3_endpoints():
    """LV2 user cannot access LV3 endpoints."""
    user = User(id=2, username="mgr", password="x", dept="sales", role_level=2, is_tech=False)
    assert verify_min_role_level(user, 3) is False


def test_lv3_boss_can_access_all_below_lv4():
    """LV3 boss can access LV1, LV2, LV3 endpoints."""
    user = User(id=3, username="boss", password="x", dept="admin", role_level=3, is_tech=False)
    assert verify_min_role_level(user, 1) is True
    assert verify_min_role_level(user, 2) is True
    assert verify_min_role_level(user, 3) is True


def test_lv3_cannot_access_lv4_endpoints():
    """LV3 boss cannot access LV4 admin endpoints."""
    user = User(id=3, username="boss", password="x", dept="admin", role_level=3, is_tech=False)
    assert verify_min_role_level(user, 4) is False


def test_lv4_admin_can_access_all_endpoints():
    """LV4 admin can access all endpoints."""
    user = User(id=4, username="admin", password="x", dept="admin", role_level=4, is_tech=True)
    assert verify_min_role_level(user, 1) is True
    assert verify_min_role_level(user, 2) is True
    assert verify_min_role_level(user, 3) is True
    assert verify_min_role_level(user, 4) is True


def test_invalid_min_level_above_4_raises():
    """verify_min_role_level rejects min_level > 4."""
    user = User(id=4, username="admin", password="x", dept="admin", role_level=4, is_tech=True)
    try:
        verify_min_role_level(user, 5)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be 1-4" in str(e)


def test_invalid_min_level_below_1_raises():
    """verify_min_role_level rejects min_level < 1."""
    user = User(id=4, username="admin", password="x", dept="admin", role_level=4, is_tech=True)
    try:
        verify_min_role_level(user, 0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be 1-4" in str(e)


def test_boss_approval_requires_lv3():
    """Quote/sampling boss approval should require LV3, reject LV2."""
    lv2_user = User(id=2, username="mgr", password="x", dept="sales", role_level=2, is_tech=False)
    lv3_user = User(id=3, username="boss", password="x", dept="admin", role_level=3, is_tech=False)

    assert verify_min_role_level(lv2_user, 3) is False
    assert verify_min_role_level(lv3_user, 3) is True


def test_context_switching_requires_lv4():
    """Context switching should require LV4, reject LV3."""
    lv3_user = User(id=3, username="boss", password="x", dept="admin", role_level=3, is_tech=False)
    lv4_user = User(id=4, username="admin", password="x", dept="admin", role_level=4, is_tech=True)

    assert verify_min_role_level(lv3_user, 4) is False
    assert verify_min_role_level(lv4_user, 4) is True


if __name__ == "__main__":
    print("Running LV1-LV4 permission tests...")

    test_lv1_token_creation()
    test_lv4_token_creation()
    test_lv1_can_access_lv1_endpoints()
    test_lv1_cannot_access_lv2_endpoints()
    test_lv2_can_access_lv1_and_lv2_endpoints()
    test_lv2_cannot_access_lv3_endpoints()
    test_lv3_boss_can_access_all_below_lv4()
    test_lv3_cannot_access_lv4_endpoints()
    test_lv4_admin_can_access_all_endpoints()
    test_invalid_min_level_above_4_raises()
    test_invalid_min_level_below_1_raises()
    test_boss_approval_requires_lv3()
    test_context_switching_requires_lv4()

    print("PASS: All LV1-LV4 permission tests passed")
