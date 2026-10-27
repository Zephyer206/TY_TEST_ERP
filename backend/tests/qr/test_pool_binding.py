"""Pool/print/binding rejection, transaction and real concurrency acceptance."""
import asyncio
import base64
import io
from types import SimpleNamespace

from PIL import Image
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import product_box as m
from app.models.audit import AuditLog
from app.models.warehouse import QRScanLog
from app.models.user import User
from app.services import product_box_service as service, qr_print_service as printing
from app.services.qr_transaction_service import QrError
from .service_fixtures import ACTORS, create_service_fixture, seed_service_fixture


def actor(identity):
    dept, level, _ = ACTORS[identity]
    return SimpleNamespace(id=identity, dept=dept, role_level=level)


async def generate(db, count=1, key="generate-request-0001"):
    return await service.generate_batch(db, actor(102), count=count, idempotency_key=key)


async def bind(db, payload, *, who=103, product=801, key="binding-request-0001", context=None):
    return await service.bind_box(db, actor(who), qr_payload=payload, order_product_id=product,
                                  context_id=context, idempotency_key=key)


@pytest.mark.asyncio
async def test_generate_500_stable_unique_identities_and_replay(service_db):
    result = await generate(service_db, 500)
    assert len(result["items"]) == result["count"] == 500
    assert len({i["qr_payload"] for i in result["items"]}) == 500
    for item in result["items"]:
        assert item["qr_payload"] == f'PFB:v1:{item["id"]}:{item["public_code"]}'
        assert item["public_code"].split("-")[-1] == f'{int(item["id"]):06}'
    assert await generate(service_db, 500) == result
    assert await service_db.scalar(select(func.count()).select_from(m.ProductQrPoolItem)) == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, -1, 501, True, 1.5])
async def test_invalid_batch_is_rejected_without_partial_records(service_db, count):
    with pytest.raises(QrError) as caught:
        await generate(service_db, count)
    assert caught.value.code == "INVALID_QUANTITY"
    assert await service_db.scalar(select(func.count()).select_from(m.ProductQrPoolItem)) == 0
    assert await service_db.scalar(select(func.count()).select_from(m.QrIdempotencyRecord)) == 0


@pytest.mark.asyncio
async def test_configured_server_limit_is_enforced(service_db, monkeypatch):
    monkeypatch.setattr(service.settings, "PRODUCT_QR_BATCH_LIMIT", 2)
    with pytest.raises(QrError):
        await generate(service_db, 3)
    assert (await generate(service_db, 2))["count"] == 2


@pytest.mark.asyncio
async def test_binding_is_one_box_one_order_and_replay_is_not_a_second_event(service_db):
    item = (await generate(service_db))["items"][0]
    result = await bind(service_db, item["qr_payload"])
    box = result["box"]
    assert box["order_id"] == 401 and box["part_id"] == 301 and box["customer_id"] == 201
    assert box["current_qty"] == 0 and box["qr_payload"] == item["qr_payload"]
    assert box["bound_by"] == 103
    assert await bind(service_db, item["qr_payload"]) == result
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 1
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent)) == 1
    for product in (801, 803):
        with pytest.raises(QrError) as caught:
            await bind(service_db, item["qr_payload"], product=product, key=f"bind-another-{product}")
        assert caught.value.code == "QR_ALREADY_BOUND"
    scanned = await service.scan_box(service_db, actor(103), qr_payload=item["qr_payload"])
    assert scanned["box"]["id"] == box["id"] and "bind" not in scanned["allowed_actions"]
    with pytest.raises(QrError) as caught:
        await service.scan_box(service_db, actor(105), qr_payload=item["qr_payload"])
    assert caught.value.code == "FORBIDDEN"
    assert (await service.scan_box(service_db, actor(104), qr_payload=item["qr_payload"]))["box"]["id"] == box["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,code", [
    ("MAT:1:20261023", "INVALID_QR"), ("PFB:v2:1:PFB-20261023-000001", "INVALID_QR"),
    ("PFB:v1:01:PFB-20261023-000001", "INVALID_QR"),
    ("PFB:v1:999999:PFB-20261023-999999", "QR_NOT_IN_POOL"),
])
async def test_pool_outside_and_malformed_payloads_cannot_bind_or_create_audit(service_db, payload, code):
    with pytest.raises(QrError) as caught:
        await bind(service_db, payload)
    assert caught.value.code == code and payload not in str(caught.value)
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 0
    assert await service_db.scalar(select(func.count()).select_from(QRScanLog)) == 0


@pytest.mark.asyncio
async def test_full_payload_is_verified_and_conversion_targets_cannot_bind_directly(service_db):
    item = (await generate(service_db))["items"][0]
    changed = item["qr_payload"].replace(item["public_code"].split("-")[1], "20200101")
    with pytest.raises(QrError) as caught:
        await bind(service_db, changed)
    assert caught.value.code == "INVALID_QR"
    with pytest.raises(QrError) as caught:
        await bind(service_db, item["qr_payload"], product=802)
    assert caught.value.code == "INVALID_PRODUCT"


@pytest.mark.asyncio
async def test_missing_owner_or_machine_configuration_blocks_binding(service_db):
    item = (await generate(service_db))["items"][0]
    await service_db.execute(m.ProductOrderContext.__table__.update().where(
        m.ProductOrderContext.order_id == 401).values(business_owner_id=None))
    with pytest.raises(QrError) as caught:
        await bind(service_db, item["qr_payload"])
    assert caught.value.code == "STATE_CONFLICT" and "business_owner" in caught.value.details["missing_configuration"]
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 0


@pytest.mark.asyncio
async def test_production_binding_requires_own_live_matching_selected_context(service_db):
    item = (await generate(service_db))["items"][0]
    with pytest.raises(QrError):
        await bind(service_db, item["qr_payload"], who=101)
    context = m.MachineProductionContext(user_id=101, machine_id=601, scan_ticket_digest="c" * 64,
        state_id=1001, expires_at=func.clock_timestamp() + text("interval '30 minutes'"))
    service_db.add(context)
    await service_db.flush()
    with pytest.raises(QrError):
        await bind(service_db, item["qr_payload"], who=102, context=context.id)
    result = await bind(service_db, item["qr_payload"], who=101, context=context.id)
    assert result["box"]["bound_by"] == 101


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_context", ["other_user", "expired", "wrong_machine", "completed", "closed_assignment"])
async def test_invalid_production_context_cannot_bind_or_leave_partial_facts(service_db, invalid_context):
    item = (await generate(service_db))["items"][0]
    context = m.MachineProductionContext(user_id=103 if invalid_context == "other_user" else 101,
        machine_id=602 if invalid_context == "wrong_machine" else 601, scan_ticket_digest="d" * 64,
        state_id=1001,
        scanned_at=func.clock_timestamp() + text("interval '-31 minutes'"),
        last_activity_at=func.clock_timestamp() + text("interval '-31 minutes'"),
        expires_at=func.clock_timestamp() + text(
            "interval '-1 minute'" if invalid_context == "expired" else "interval '30 minutes'"))
    service_db.add(context)
    await service_db.flush()
    if invalid_context == "completed":
        await service_db.execute(m.MachineOrderProcessState.__table__.update().where(
            m.MachineOrderProcessState.id == 1001).values(production_status="completed",
                completed_by=101, completed_at=func.clock_timestamp()))
    if invalid_context == "closed_assignment":
        from app.models.production import PlanMachineAssignment
        await service_db.execute(PlanMachineAssignment.__table__.update().where(
            PlanMachineAssignment.id == 501).values(is_active=False))
    with pytest.raises(QrError) as caught:
        await bind(service_db, item["qr_payload"], who=101, context=context.id)
    assert caught.value.code in {"FORBIDDEN", "STATE_CONFLICT"}
    assert await service_db.scalar(select(func.count()).select_from(m.ProductBox)) == 0
    assert await service_db.scalar(select(func.count()).select_from(m.ProductFlowEvent)) == 0


@pytest.mark.asyncio
async def test_replay_does_not_bypass_revoked_permission(service_db):
    await generate(service_db)
    await service_db.execute(m.QrCapabilityGrant.__table__.update().where(
        m.QrCapabilityGrant.user_id == 102, m.QrCapabilityGrant.capability == "qr.generate",
        m.QrCapabilityGrant.revoked_at.is_(None)).values(revoked_at=func.clock_timestamp(), revoked_by=107))
    with pytest.raises(QrError) as caught:
        await generate(service_db)
    assert caught.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_print_request_cancel_confirmation_and_reprint_keep_identity(service_db):
    item = (await generate(service_db))["items"][0]
    job = await printing.print_data(service_db, actor(103), item_ids=[int(item["id"])],
                                    idempotency_key="print-request-0001")
    assert job["template"]["columns"] == 3 and job["template"]["rows"] == 7
    assert job["items"][0]["qr_payload"] == item["qr_payload"]
    with Image.open(io.BytesIO(base64.b64decode(job["items"][0]["qr_image_base64"].split(",")[1]))) as png:
        assert png.format == "PNG" and png.width == png.height
        assert png.convert("L").getpixel((0, 0)) == 255
    # Data delivery, including opening then cancelling the dialog, is not print success.
    assert (await service_db.get(m.ProductQrPoolItem, int(item["id"]))).__dict__["print_count"] == 0
    with pytest.raises(QrError):
        await printing.confirm_print(service_db, actor(107), print_job_id=int(job["print_job_id"]),
            confirmed_item_ids=[int(item["id"])], idempotency_key="wrong-user-confirm")
    bound = await bind(service_db, item["qr_payload"])
    confirmed = await printing.confirm_print(service_db, actor(103), print_job_id=int(job["print_job_id"]),
        confirmed_item_ids=[int(item["id"])], idempotency_key="print-confirm-0001")
    assert confirmed["items"][0]["print_count"] == 1
    assert confirmed["items"][0]["bound_box_id"] == bound["box"]["id"]
    assert await printing.confirm_print(service_db, actor(103), print_job_id=int(job["print_job_id"]),
        confirmed_item_ids=[int(item["id"])], idempotency_key="print-confirm-0001") == confirmed
    once_more = await printing.confirm_print(service_db, actor(103), print_job_id=int(job["print_job_id"]),
        confirmed_item_ids=[int(item["id"])], idempotency_key="print-confirm-0002")
    assert once_more["items"][0]["print_count"] == 1
    reprint = await printing.reprint(service_db, actor(103), item_id=int(item["id"]), idempotency_key="reprint-request-01")
    assert reprint["print_job_id"] != job["print_job_id"]
    assert reprint["items"][0]["qr_payload"] == item["qr_payload"]
    assert await service_db.scalar(select(func.count()).select_from(m.ProductQrPoolItem)) == 1


@pytest.mark.asyncio
async def test_invalid_confirmation_rolls_back_all_items(service_db):
    items = (await generate(service_db, 2))["items"]
    job = await printing.print_data(service_db, actor(103), item_ids=[int(items[0]["id"])], idempotency_key="print-one-only-01")
    with pytest.raises(QrError):
        await printing.confirm_print(service_db, actor(103), print_job_id=int(job["print_job_id"]),
            confirmed_item_ids=[int(i["id"]) for i in items], idempotency_key="confirm-invalid-01")
    assert await service_db.scalar(select(func.count()).select_from(m.QrPrintConfirmation)) == 0
    assert list((await service_db.execute(select(m.ProductQrPoolItem.print_count))).scalars()) == [0, 0]


@pytest.mark.asyncio
@pytest.mark.parametrize("same_key", [True, False])
async def test_concurrent_binding_has_one_identity_and_at_most_one_success(qr_database_factory, same_key):
    with qr_database_factory() as sync_engine:
        with sync_engine.begin() as connection:
            create_service_fixture(connection)
        with sync_engine.begin() as connection:
            seed_service_fixture(connection)
        engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"), echo=False, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                item = (await generate(session))["items"][0]
                await session.commit()
            async def attempt(index):
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    try:
                        user = await session.get(User, 103 if same_key or index == 1 else 101)
                        result = await service.bind_box(session, user, qr_payload=item["qr_payload"], order_product_id=801,
                            idempotency_key="concurrent-same-01" if same_key else f"concurrent-key-{index}")
                        await session.commit()
                        return result
                    except QrError as error:
                        await session.rollback()
                        return error.code
            # Different request keys still contend on the same pool row. Use two
            # authorized warehouse actors rather than relying on a denied role.
            if not same_key:
                async with AsyncSession(engine) as session:
                    await session.execute(User.__table__.update().where(User.id == 101).values(dept="warehouse"))
                    session.add(m.QrCapabilityGrant(user_id=101, capability="qr.bind", granted_by=107))
                    await session.commit()
            results = await asyncio.wait_for(asyncio.gather(attempt(1), attempt(2)), timeout=20)
            successful = [r for r in results if isinstance(r, dict)]
            assert len(successful) == (2 if same_key else 1)
            if same_key:
                assert results[0] == results[1]
            else:
                assert "QR_ALREADY_BOUND" in results
            async with AsyncSession(engine) as session:
                assert await session.scalar(select(func.count()).select_from(m.ProductBox)) == 1
                assert await session.scalar(select(func.count()).select_from(m.ProductFlowEvent)) == 1
        finally:
            await engine.dispose()
