"""Execute the actual Alembic revision against owned PostgreSQL databases.

These tests accept the persistence foundation, not the future HTTP/UI workflows.
Legacy prerequisites are synthetic; replaying every historical migration and
real material workflows remains a separate release regression task.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import product_box as m
from app.models.warehouse import QRScanLog, ScanOperation, ScanType
from .conftest import ROOT, create_legacy_fixture, load_migration, run_migration


def add(connection, cls, **values):
    return connection.execute(cls.__table__.insert().values(**values).returning(cls.id)).scalar_one()


def pool(connection):
    identity = connection.execute(text(
        "SELECT nextval(pg_get_serial_sequence('product_qr_pool_items','id'))"
    )).scalar_one()
    code = f"PFB-20261023-{identity:06}"
    return add(connection, m.ProductQrPoolItem, id=identity, public_code=code,
               qr_payload=f"PFB:v1:{identity}:{code}", created_by=1)


def configuration(connection):
    route = add(connection, m.ProductRouteRevision, route_code=uuid4().hex, revision=1,
                product_code="B", steps_json=[{"code": "CUT", "machines": [1]}],
                first_output_process_code="CUT", created_by=1)
    product = add(connection, m.ProductOrderProduct, order_id=1, part_id=1,
                  product_code="B", target_qty=100, route_revision_id=route, configured_by=1)
    return route, product


def box(connection, *, config=None, pool_id=None, **overrides):
    route, product = config or configuration(connection)
    item = pool_id or pool(connection)
    values = dict(qr_pool_item_id=item, box_no=uuid4().hex, order_id=1,
                  order_product_id=product, part_id=1, product_code="B",
                  product_name_snapshot="Synthetic B", route_revision_id=route,
                  current_qty=100, bound_by=1)
    values.update(overrides)
    identity = add(connection, m.ProductBox, **values)
    connection.execute(m.ProductQrPoolItem.__table__.update().where(
        m.ProductQrPoolItem.id == item).values(pool_status="bound"))
    return dict(box=identity, pool=item, route=route, product=product)


def process(connection, seed):
    state = add(connection, m.MachineOrderProcessState, assignment_id=1,
                order_product_id=seed["product"], route_revision_id=seed["route"],
                process_code="CUT", target_qty=100)
    quantity = add(connection, m.BoxProcessQuantity, state_id=state,
                   box_id=seed["box"], current_qty=100, updated_by=1, material_batch_id=1)
    return state, quantity


def conversion_target(connection, source_product):
    route = add(connection, m.ProductRouteRevision, route_code=uuid4().hex, revision=1,
                product_code="C", steps_json=[{"code": "COAT"}], first_output_process_code="COAT", created_by=1)
    return add(connection, m.ProductOrderProduct, order_id=1, part_id=2,
               product_code="C", target_qty=0, route_revision_id=route,
               binding_allowed=False, conversion_source_id=source_product, configured_by=1)


def rejected(connection, action, *, constraint=None):
    with pytest.raises(IntegrityError) as caught:
        with connection.begin_nested():
            action()
            connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    if constraint:
        assert caught.value.orig.diag.constraint_name == constraint


def test_migration_is_frozen_and_matches_parent():
    revision = load_migration()
    assert revision.down_revision == "20261020_ppap"
    assert revision.revision == "20261022_product_box_foundation"
    assert set(revision.TABLES) == {table.name for table in m.DOMAIN_TABLES}
    assert len(revision.TABLES) == 23


def test_real_migration_matches_orm_columns_keys_and_indexes(qr_connection):
    inspector = inspect(qr_connection)
    for table in m.DOMAIN_TABLES:
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        assert set(columns) == {c.name for c in table.columns}, table.name
        for column in table.columns:
            actual = columns[column.name]
            assert actual["nullable"] == column.nullable, (table.name, column.name)
            if str(column.type).startswith("DATETIME") or "TIMESTAMP" in str(column.type):
                assert actual["type"].timezone, (table.name, column.name)
        actual_fk = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]))
                     for f in inspector.get_foreign_keys(table.name)}
        expected_fk = {(tuple(c.name for c in f.columns), f.referred_table.name,
                        tuple(e.column.name for e in f.elements)) for f in table.foreign_key_constraints}
        assert expected_fk == actual_fk, table.name
        actual_unique = {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table.name)}
        expected_unique = {tuple(c.name for c in u.columns) for u in table.constraints
                           if u.__class__.__name__ == "UniqueConstraint"}
        assert expected_unique == actual_unique, table.name
        indexes = {i["name"] for i in inspector.get_indexes(table.name)}
        assert {i.name for i in table.indexes} <= indexes, table.name


def test_old_scan_row_and_enum_mapping_survive(qr_connection):
    with Session(bind=qr_connection) as session:
        old = session.scalars(select(QRScanLog)).one()
        assert old.scan_type == ScanType.MAT and old.operation == ScanOperation.QUERY
        assert old.entity_id == 1 and old.notes == "legacy sentinel"
    for name in ("users", "parts", "customers", "machines", "material_batches",
                 "production_plans", "plan_machine_assignments"):
        assert qr_connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one() == 2


def test_new_scan_type_and_bigint_identity_roundtrip(qr_connection):
    identity = qr_connection.execute(QRScanLog.__table__.insert().values(
        scan_type=ScanType.PFB, entity_id=3_000_000_000, entity_no="PFB-SYNTHETIC",
        operator_id=1, operation=ScanOperation.BIND,
        scanned_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ).returning(QRScanLog.id)).scalar_one()
    with Session(bind=qr_connection) as session:
        row = session.get(QRScanLog, identity)
        assert row.entity_id == 3_000_000_000 and row.scan_type == ScanType.PFB
        assert row.operation == ScanOperation.BIND


@pytest.mark.parametrize("field,value", [("current_qty", -1), ("version", 0), ("product_code", "A")])
def test_invalid_box_values_rejected(qr_connection, field, value):
    config = configuration(qr_connection)
    item = pool(qr_connection)
    rejected(qr_connection, lambda: box(qr_connection, config=config, pool_id=item, **{field: value}))


def test_one_pool_cannot_bind_two_boxes(qr_connection):
    seed = box(qr_connection)
    rejected(qr_connection, lambda: box(qr_connection, config=(seed["route"], seed["product"]),
                                       pool_id=seed["pool"]))
    assert qr_connection.execute(select(m.ProductBox.id)).all() == [(seed["box"],)]


@pytest.mark.parametrize("field", ["public_code", "qr_payload"])
def test_pool_identifiers_are_globally_unique(qr_connection, field):
    item = pool(qr_connection)
    original = qr_connection.execute(select(m.ProductQrPoolItem.__table__).where(
        m.ProductQrPoolItem.id == item)).mappings().one()
    values = dict(public_code="PFB-OTHER", qr_payload="PFB:v1:999:PFB-OTHER", created_by=1)
    values[field] = original[field]
    rejected(qr_connection, lambda: add(qr_connection, m.ProductQrPoolItem, **values))


def test_box_cannot_claim_another_orders_product(qr_connection):
    config = configuration(qr_connection)
    item = pool(qr_connection)
    rejected(qr_connection, lambda: box(qr_connection, config=config, pool_id=item, order_id=2),
             constraint="fk_pfb_box_product")


def test_binding_state_must_match_box_at_transaction_end(qr_connection):
    item = pool(qr_connection)
    rejected(qr_connection, lambda: qr_connection.execute(
        m.ProductQrPoolItem.__table__.update().where(m.ProductQrPoolItem.id == item).values(pool_status="bound")))
    assert qr_connection.execute(select(m.ProductQrPoolItem.pool_status).where(
        m.ProductQrPoolItem.id == item)).scalar_one() == "unused"


@pytest.mark.parametrize("field,value", [("public_code", "REPLACED"), ("qr_payload", "REPLACED"),
                                        ("payload_version", "v2"), ("pool_status", "void")])
def test_pool_identity_cannot_be_rewritten(qr_connection, field, value):
    seed = box(qr_connection)
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductQrPoolItem.__table__.update().where(
        m.ProductQrPoolItem.id == seed["pool"]).values(**{field: value})))


def test_bound_box_order_and_identity_cannot_be_changed_or_deleted(qr_connection):
    seed = box(qr_connection)
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductBox.__table__.update().where(
        m.ProductBox.id == seed["box"]).values(order_id=2)))
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductBox.__table__.delete().where(
        m.ProductBox.id == seed["box"])))
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductQrPoolItem.__table__.delete().where(
        m.ProductQrPoolItem.id == seed["pool"])))


def test_published_route_cannot_be_overwritten(qr_connection):
    seed = box(qr_connection)
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductRouteRevision.__table__.update().where(
        m.ProductRouteRevision.id == seed["route"]).values(revision=2)))


def test_event_history_is_append_only(qr_connection):
    seed = box(qr_connection)
    event = add(qr_connection, m.ProductFlowEvent, product_box_id=seed["box"], event_type="bind",
                order_id=1, order_product_id=seed["product"], operator_id=1,
                before_qty=0, after_qty=100, box_version=1)
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductFlowEvent.__table__.update().where(
        m.ProductFlowEvent.id == event).values(after_qty=200)))
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductFlowEvent.__table__.delete().where(
        m.ProductFlowEvent.id == event)))


def test_quantity_allocation_sum_and_source_are_enforced(qr_connection):
    seed = box(qr_connection)
    _, quantity = process(qr_connection, seed)
    base = dict(source_quantity_id=quantity, order_id=1, order_product_id=seed["product"],
                box_id=seed["box"], available_qty=100, remaining_order_qty_snapshot=80,
                order_qty=80, stock_qty=20, assigned_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.ProductOutputAllocation, **(base | {"stock_qty": 30})),
             constraint="ck_pfb_allocation_quantity")
    allocation = add(qr_connection, m.ProductOutputAllocation, **base)
    rejected(qr_connection, lambda: add(qr_connection, m.ProductOutputAllocation, **base))
    assert allocation > 0


def test_split_relation_requires_distinct_boxes_and_conserved_purpose(qr_connection):
    parent = box(qr_connection)
    child = box(qr_connection, config=(parent["route"], parent["product"]))
    base = dict(parent_box_id=parent["box"], child_box_id=child["box"], relation_type="split",
                quantity=30, order_qty=20, stock_qty=10, source_order_id=1, target_order_id=1,
                source_order_product_id=parent["product"], target_order_product_id=parent["product"],
                source_product_code="B", target_product_code="B", source_snapshot={}, created_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.ProductBoxRelation,
                                       **(base | {"child_box_id": parent["box"]})))
    rejected(qr_connection, lambda: add(qr_connection, m.ProductBoxRelation, **(base | {"quantity": 31})))
    relation = add(qr_connection, m.ProductBoxRelation, **base)
    rejected(qr_connection, lambda: qr_connection.execute(m.ProductBoxRelation.__table__.update().where(
        m.ProductBoxRelation.id == relation).values(quantity=40, stock_qty=20)))


def test_pending_conversion_cannot_claim_actual_output(qr_connection):
    seed = box(qr_connection)
    target = conversion_target(qr_connection, seed["product"])
    base = dict(product_box_id=seed["box"], order_id=1, source_order_product_id=seed["product"],
                target_order_product_id=target, source_product_code="B", target_product_code="C",
                proposed_qty=100, trigger_type="manual", created_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.ProductConversionRecord, **(base | {"actual_qty": 30})))
    rejected(qr_connection, lambda: add(qr_connection, m.ProductConversionRecord,
        **(base | {"confirmation_status": "confirmed", "confirmed_by": 1,
                   "confirmed_at": datetime.now(timezone.utc)})))
    conversion = add(qr_connection, m.ProductConversionRecord, **base)
    assert qr_connection.execute(select(m.ProductConversionRecord.actual_qty).where(
        m.ProductConversionRecord.id == conversion)).scalar_one() is None


def test_conversion_target_cannot_add_independent_demand(qr_connection):
    _, product = configuration(qr_connection)
    route = add(qr_connection, m.ProductRouteRevision, route_code=uuid4().hex, revision=1,
                product_code="C", steps_json=[{"code": "COAT"}], first_output_process_code="COAT", created_by=1)
    values = dict(order_id=1, part_id=2, product_code="C", target_qty=0, route_revision_id=route,
                  binding_allowed=False, conversion_source_id=product, configured_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.ProductOrderProduct, **(values | {"target_qty": 20})))
    assert add(qr_connection, m.ProductOrderProduct, **values) > 0


def test_active_capability_unique_but_revoked_history_is_retained(qr_connection):
    values = dict(user_id=1, capability="qr.print", granted_by=2)
    grant = add(qr_connection, m.QrCapabilityGrant, **values)
    rejected(qr_connection, lambda: add(qr_connection, m.QrCapabilityGrant, **values))
    qr_connection.execute(m.QrCapabilityGrant.__table__.update().where(m.QrCapabilityGrant.id == grant).values(
        revoked_at=text("CURRENT_TIMESTAMP"), revoked_by=2))
    assert add(qr_connection, m.QrCapabilityGrant, **values) != grant


def test_print_confirmation_requires_job_item_and_is_unique(qr_connection):
    item = pool(qr_connection)
    job = add(qr_connection, m.QrPrintJob, requested_by=1, template_code="a4_3x7_v1", request_type="initial")
    values = dict(job_id=job, pool_item_id=item, confirmed_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.QrPrintConfirmation, **values))
    add(qr_connection, m.QrPrintJobItem, job_id=job, pool_item_id=item, display_snapshot={})
    rejected(qr_connection, lambda: add(qr_connection, m.QrPrintConfirmation,
                                       **(values | {"confirmed_by": 2})), constraint="fk_pfb_print_requester")
    add(qr_connection, m.QrPrintConfirmation, **values)
    rejected(qr_connection, lambda: add(qr_connection, m.QrPrintConfirmation, **values))
    assert qr_connection.execute(select(m.ProductQrPoolItem.print_count).where(
        m.ProductQrPoolItem.id == item)).scalar_one() == 0  # Increment belongs to the future confirmation transaction.


def test_idempotency_is_scoped_unique_and_preserves_committed_result(qr_connection):
    values = dict(operator_id=1, action="bind", entity_key="pool:1", request_key="synthetic-key",
                  request_digest="a" * 64, response_json={"box_id": 1}, http_status=201)
    identity = add(qr_connection, m.QrIdempotencyRecord, **values)
    rejected(qr_connection, lambda: add(qr_connection, m.QrIdempotencyRecord, **values))
    assert add(qr_connection, m.QrIdempotencyRecord, **(values | {"operator_id": 2})) != identity
    rejected(qr_connection, lambda: qr_connection.execute(m.QrIdempotencyRecord.__table__.update().where(
        m.QrIdempotencyRecord.id == identity).values(response_json={})))


def test_scan_context_has_real_lifetime(qr_connection):
    now = datetime.now(timezone.utc)
    values = dict(user_id=1, machine_id=1, scan_ticket_digest="b" * 64,
                  scanned_at=now, expires_at=now + timedelta(minutes=30))
    rejected(qr_connection, lambda: add(qr_connection, m.MachineProductionContext,
                                       **(values | {"expires_at": now})))
    assert add(qr_connection, m.MachineProductionContext, **values) > 0


def test_exception_confirmation_and_recipient_resolution_are_independent(qr_connection):
    seed = box(qr_connection)
    state, _ = process(qr_connection, seed)
    values = dict(order_id=1, state_id=state, material_batch_id=1, expected_spec={"width": 10},
                  actual_spec={"width": 12}, active_dedupe_key="e" * 64, created_by=1)
    rejected(qr_connection, lambda: add(qr_connection, m.CoilSpecException,
                                       **(values | {"status": "confirmed"})))
    exception = add(qr_connection, m.CoilSpecException, **values)
    group_values = dict(exception_id=exception, group_type="business_owner")
    group = add(qr_connection, m.ExceptionRecipientGroup, **group_values)
    rejected(qr_connection, lambda: qr_connection.execute(m.ExceptionRecipientGroup.__table__.update().where(
        m.ExceptionRecipientGroup.id == group).values(resolution_status="resolved")))
    qr_connection.execute(m.ExceptionRecipientGroup.__table__.update().where(
        m.ExceptionRecipientGroup.id == group).values(resolution_status="resolved", recipient_ids=[2],
                                                     resolved_at=datetime.now(timezone.utc)))
    assert qr_connection.execute(select(m.CoilSpecException.status)).scalar_one() == "pending_confirmation"


def test_notification_cannot_be_persisted_for_wrong_recipient(qr_connection):
    seed = box(qr_connection)
    state, _ = process(qr_connection, seed)
    exception = add(qr_connection, m.CoilSpecException, order_id=1, state_id=state,
                    material_batch_id=1, expected_spec={"width": 10}, actual_spec={"width": 12},
                    active_dedupe_key="f" * 64, created_by=1)
    values = dict(dedupe_key="synthetic-notification", recipient_user_id=1,
                  exception_id=exception, event_type="spec_exception", payload_json={})
    outbox = add(qr_connection, m.NotificationOutbox, **values)
    rejected(qr_connection, lambda: add(qr_connection, m.QrNotification,
        outbox_id=outbox, recipient_user_id=2, payload_json={}), constraint="fk_pfb_notification_recipient")
    add(qr_connection, m.QrNotification, outbox_id=outbox, recipient_user_id=1, payload_json={})
    rejected(qr_connection, lambda: add(qr_connection, m.NotificationOutbox, **values))
    rejected(qr_connection, lambda: qr_connection.execute(m.NotificationOutbox.__table__.update().where(
        m.NotificationOutbox.id == outbox).values(status="sent")), constraint="ck_pfb_delivery_sent")
    attempt = add(qr_connection, m.QrNotificationAttempt, outbox_id=outbox, attempt_no=1,
                  trigger_type="automatic", result="failed", safe_error_code="TEST_FAILURE")
    rejected(qr_connection, lambda: add(qr_connection, m.QrNotificationAttempt, outbox_id=outbox,
        attempt_no=6, trigger_type="automatic", result="failed"), constraint="ck_pfb_attempt_number")
    rejected(qr_connection, lambda: qr_connection.execute(m.QrNotificationAttempt.__table__.delete().where(
        m.QrNotificationAttempt.id == attempt)))


def test_empty_upgrade_downgrade_upgrade_preserves_legacy_rows(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_legacy_fixture(connection)
            run_migration(connection, "upgrade")
        with engine.begin() as connection:
            run_migration(connection, "downgrade")
        with engine.begin() as connection:
            assert not (set(load_migration().TABLES) & set(inspect(connection).get_table_names()))
            assert str(inspect(connection).get_columns("qr_scan_logs")[2]["type"]) == "INTEGER"
            assert connection.execute(text("SELECT notes FROM qr_scan_logs")).scalar_one() == "legacy sentinel"
            run_migration(connection, "upgrade")
        with engine.connect() as connection:
            assert set(load_migration().TABLES) <= set(inspect(connection).get_table_names())


def test_historic_varchar_scan_columns_remain_supported(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_legacy_fixture(connection, native_enums=False)
            run_migration(connection, "upgrade")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT notes FROM qr_scan_logs")).scalar_one() == "legacy sentinel"
            assert str(inspect(connection).get_columns("qr_scan_logs")[1]["type"]) == "VARCHAR(20)"


def test_downgrade_with_identity_refuses_data_loss(qr_connection):
    item = pool(qr_connection)
    with pytest.raises(RuntimeError, match="preserve identities and audit"):
        run_migration(qr_connection, "downgrade")
    assert qr_connection.execute(select(m.ProductQrPoolItem.id)).all() == [(item,)]


def test_downgrade_with_new_scan_audit_is_refused(qr_connection):
    qr_connection.execute(QRScanLog.__table__.insert().values(
        scan_type=ScanType.PFB, entity_id=1, operator_id=1, operation=ScanOperation.BIND,
        scanned_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    with pytest.raises(RuntimeError, match="preserve new scan audit"):
        run_migration(qr_connection, "downgrade")
    assert set(load_migration().TABLES) <= set(inspect(qr_connection).get_table_names())


def test_aborted_upgrade_rolls_back_all_ddl(qr_database_factory):
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_legacy_fixture(connection)
        with pytest.raises(RuntimeError, match="synthetic migration abort"):
            with engine.begin() as connection:
                run_migration(connection, "upgrade")
                raise RuntimeError("synthetic migration abort")
        with engine.begin() as connection:
            assert not (set(load_migration().TABLES) & set(inspect(connection).get_table_names()))
            entity = next(c for c in inspect(connection).get_columns("qr_scan_logs") if c["name"] == "entity_id")
            assert str(entity["type"]) == "INTEGER"
            assert connection.execute(text("SELECT notes FROM qr_scan_logs")).scalar_one() == "legacy sentinel"
            run_migration(connection, "upgrade")


def test_standard_alembic_commands_use_only_the_supplied_test_connection(qr_database_factory):
    revision = load_migration()
    config = Config(str(ROOT / "alembic.ini"))
    with qr_database_factory() as engine:
        with engine.begin() as connection:
            create_legacy_fixture(connection)
            config.attributes["connection"] = connection
            # Synthetic fixture represents the required pre-existing schema.
            # Do not replay unrelated historical migrations against this fixture.
            command.stamp(config, revision.down_revision)
            command.upgrade(config, revision.revision)
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == revision.revision
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, revision.down_revision)
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == revision.down_revision
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision.revision)
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == revision.revision
            assert set(revision.TABLES) <= set(inspect(connection).get_table_names())
