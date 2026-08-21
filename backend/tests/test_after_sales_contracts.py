from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.gaibo_after_sales import (
    _aggregate_package_display_values,
    _default_workspace_view_config,
    _flush_or_conflict,
    _join_package_display_values,
    _normalize_workspace_view_config,
    _parse_column_filters,
    _normalize_requirement_updates,
    _validate_extra_data,
)
from app.models.gaibo import GaiboCustomerWorkspace
from app.schemas.gaibo import (
    GaiboCustomFieldDefinition,
    GaiboDocumentStatusUpdate,
    GaiboDrawingCreate,
    GaiboDrawingResponse,
    GaiboDrawingUpdate,
    GaiboPackageUpdate,
    GaiboPackageItemCreate,
    GaiboProcessRouteUpdate,
    GaiboSearchItem,
    GaiboSearchPage,
    GaiboSinglePartCreate,
    GaiboSinglePartResponse,
    GaiboViewPreferenceUpdate,
    GaiboWorkspaceViewConfig,
)


def test_drawing_patch_accepts_one_field_without_create_fields():
    payload = GaiboDrawingUpdate(status="submitted")

    assert payload.model_dump(exclude_unset=True) == {"status": "submitted"}


def test_drawing_preview_fields_are_response_only():
    assert "preview_url" in GaiboDrawingResponse.model_fields
    assert "preview_url" not in GaiboDrawingCreate.model_fields
    assert "drawing_preview_url" in GaiboSinglePartResponse.model_fields
    assert "drawing_preview_url" not in GaiboSinglePartCreate.model_fields


def test_document_patch_accepts_status_without_repeating_document_type():
    payload = GaiboDocumentStatusUpdate(status="ok")

    assert payload.model_dump(exclude_unset=True) == {"status": "ok"}


def test_process_patch_can_replace_steps():
    payload = GaiboProcessRouteUpdate.model_validate(
        {"steps": [{"sequence": 1, "operation_name": "冲压"}]}
    )

    assert payload.steps is not None
    assert payload.steps[0].operation_name == "冲压"


def test_source_metadata_is_not_a_user_edit_contract():
    assert "source_data" not in GaiboPackageUpdate.model_fields
    assert "source_data" not in GaiboDocumentStatusUpdate.model_fields


def test_package_archive_fields_are_editable_without_exposing_source_metadata():
    payload = GaiboPackageUpdate(priority=2, d_code="D100", tianyue_pn="TY-100")

    assert payload.model_dump(exclude_unset=True) == {
        "priority": 2,
        "d_code": "D100",
        "tianyue_pn": "TY-100",
    }


def test_search_contract_keeps_component_status_and_summary():
    item = GaiboSearchItem.model_validate(
        {
            "record_type": "installation_package",
            "record_id": 1,
            "workspace_id": 1,
            "workspace_name": "FMG 墨西哥",
            "customer_part_number": "MU100",
            "priority": 1,
            "d_code": "D100",
            "tianyue_pn": "TY-100",
            "component_items": [
                {
                    "sequence": 1,
                    "ibi": "10001×2PCS",
                    "tianyue_internal_composition": "TYAP-Q100×2pcs",
                    "quantity": 2,
                    "status": "external_purchase",
                }
            ],
            "updated_at": datetime(2026, 8, 18),
        }
    )
    page = GaiboSearchPage(
        items=[item],
        total=1,
        page=1,
        page_size=20,
        summary={
            "total_records": 1,
            "priced_records": 0,
            "missing_price_records": 1,
            "drawing_ok_records": 0,
            "sample_ok_records": 0,
            "ppap_ok_records": 0,
        },
    )

    assert page.items[0].component_items[0].status == "external_purchase"
    assert page.summary.total_records == 1


def test_search_contract_accepts_pending_component_ibi():
    item = GaiboSearchItem.model_validate(
        {
            "record_type": "installation_package",
            "record_id": 2,
            "workspace_id": 1,
            "workspace_name": "FMG 墨西哥",
            "component_items": [
                {
                    "sequence": 1,
                    "ibi": None,
                    "tianyue_internal_composition": "GBAP-Q0487×4pcs",
                    "quantity": 4,
                }
            ],
            "updated_at": datetime(2026, 8, 21),
        }
    )

    assert item.component_items[0].ibi is None
    assert item.component_items[0].tianyue_internal_composition == "GBAP-Q0487×4pcs"


def test_package_item_contract_preserves_internal_composition_when_ibi_is_pending():
    item = GaiboPackageItemCreate(
        ibi=None,
        tianyue_internal_composition="GBAP-Q0487×4pcs",
        quantity=4,
    )

    assert item.ibi is None
    assert item.tianyue_internal_composition == "GBAP-Q0487×4pcs"


def test_column_filter_parser_preserves_multi_select_values():
    parsed = _parse_column_filters('{"status":["drawing_ok", "sample_in_progress"], "primaryNumber":"MU221821"}')

    assert parsed == {
        "status": ["drawing_ok", "sample_in_progress"],
        "primaryNumber": "MU221821",
    }


def test_view_preference_accepts_typed_frontend_configuration():
    payload = GaiboViewPreferenceUpdate(
        config={"visible": ["primaryNumber", "price"], "density": "compact"}
    )

    assert payload.config["density"] == "compact"


def test_customer_custom_field_becomes_part_of_default_table_config():
    field = GaiboCustomFieldDefinition(
        key="custom_project_code",
        label="客户项目号",
        data_type="text",
        scope="both",
        width=144,
    )

    config = _default_workspace_view_config([field])

    assert config.order[-1] == "custom_project_code"
    assert "custom_project_code" in config.visible
    assert config.widths["custom_project_code"] == 144


def test_workspace_view_config_keeps_primary_identifier_visible():
    config = _normalize_workspace_view_config(
        GaiboWorkspaceViewConfig(
            visible=["remark"],
            order=["remark"],
            widths={"remark": 88},
        ),
        [],
    )

    assert config.visible[0] == "primaryNumber"
    assert config.widths["remark"] == 88


def test_archived_custom_field_value_is_preserved_when_another_value_changes():
    workspace = GaiboCustomerWorkspace(
        after_sales_customer_id=1,
        slug="customer-1",
        display_name="客户 1",
        extra_field_definitions={
            "schema_version": 1,
            "columns": [
                {
                    "key": "custom_project_code",
                    "label": "客户项目号",
                    "data_type": "text",
                    "scope": "both",
                    "default_visible": True,
                    "width": 120,
                    "sequence": 0,
                    "is_active": True,
                    "options": [],
                }
            ],
        },
    )

    result = _validate_extra_data(
        workspace,
        {"custom_project_code": " P-200 "},
        record_type="single_part",
        existing={"custom_archived": "保留值"},
    )

    assert result == {"custom_archived": "保留值", "custom_project_code": "P-200"}


def test_custom_field_scope_rejects_wrong_record_type():
    workspace = GaiboCustomerWorkspace(
        after_sales_customer_id=1,
        slug="customer-1",
        display_name="客户 1",
        extra_field_definitions={
            "schema_version": 1,
            "columns": [
                {
                    "key": "custom_package_level",
                    "label": "安装包等级",
                    "data_type": "select",
                    "scope": "installation_package",
                    "default_visible": True,
                    "width": 120,
                    "sequence": 0,
                    "is_active": True,
                    "options": ["A", "B"],
                }
            ],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        _validate_extra_data(
            workspace,
            {"custom_package_level": "A"},
            record_type="single_part",
        )

    assert exc_info.value.status_code == 400


def test_requirement_price_cannot_be_cleared_to_null():
    with pytest.raises(HTTPException) as exc_info:
        _normalize_requirement_updates({"price": None})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "价格不能为空"


def test_package_display_values_keep_order_and_remove_duplicates():
    assert _join_package_display_values(["A", "A", " B ", None, ""]) == "A · B"
    assert _join_package_display_values([None, "  "]) is None


def test_package_display_values_are_grouped_by_package():
    assert _aggregate_package_display_values(
        [(7, "A", "X"), (7, "A", "Y"), (8, None, "Z")]
    ) == {7: ("A", "X · Y"), 8: (None, "Z")}


@pytest.mark.asyncio
async def test_database_integrity_error_becomes_a_conflict_response():
    db = SimpleNamespace(
        flush=AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("duplicate"))),
        rollback=AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _flush_or_conflict(db, "当前安装包已存在相同的资料类型")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "当前安装包已存在相同的资料类型"
    db.rollback.assert_awaited_once()
