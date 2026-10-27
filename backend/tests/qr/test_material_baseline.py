"""Existing material QR flows must survive the new domain implementation."""
import pytest
from sqlalchemy import select

from app.models.warehouse import Material, MaterialBatch, BatchStatus, BatchTransaction, IQCResult
from app.services import material_batch_service as service


async def material(db):
    row = Material(material_no="MATERIAL-REGRESSION", name="Synthetic steel", grade="SPCC")
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_material_inbound_iqc_repeated_split_and_trace_conserve_weight(service_db):
    source = await material(service_db)
    batch = await service.create_material_batch(service_db, source.id, 100, operator_id=103)
    first_code = batch.qr_code
    await service.perform_iqc(service_db, batch, IQCResult.PASSED, operator_id=103)
    first = await service.split_batch(service_db, batch, [{"weight": 30}, {"weight": 20}], operator_id=103)
    assert batch.current_weight == 50 and sum(c.current_weight for c in first) == 50
    again = await service.split_batch(service_db, batch, [{"weight": 10}], operator_id=103)
    assert batch.current_weight == 40
    children = (await service_db.execute(select(MaterialBatch).where(MaterialBatch.parent_batch_id == batch.id))).scalars().all()
    assert len(children) == 3 and len({c.qr_uid for c in children}) == 3
    assert len({c.qr_code for c in children} | {first_code}) == 4
    assert batch.qr_code == first_code
    await service.consume_material(service_db, first[0], 5, operator_id=103)
    assert first[0].current_weight == 25 and batch.current_weight == 40
    assert (await service.get_child_batch_by_id(service_db, first[0].id)).parent_batch_id == batch.id
    siblings = await service.get_sibling_batches(service_db, parent_batch_id=batch.id, exclude_id=first[0].id)
    assert len(siblings) == 2
    logs = (await service_db.execute(select(BatchTransaction).order_by(BatchTransaction.id))).scalars().all()
    assert all(row.operator_id == 103 for row in logs)
    assert sum(row.quantity_change for row in logs if row.transaction_type == "split") == -60
    assert sum(row.quantity_change for row in logs if row.transaction_type == "consume") == -5
    assert all(c.parent_batch_id == batch.id for c in first + again)


@pytest.mark.asyncio
async def test_two_material_batches_created_in_same_second_have_distinct_identities(service_db):
    source = await material(service_db)
    first = await service.create_material_batch(service_db, source.id, 10, operator_id=103)
    second = await service.create_material_batch(service_db, source.id, 10, operator_id=103)
    assert first.qr_uid != second.qr_uid and first.batch_no != second.batch_no and first.qr_code != second.qr_code


@pytest.mark.asyncio
@pytest.mark.parametrize("splits", [[], [{"weight": 0}], [{"weight": -5}], [{"weight": float("nan")}], [{"weight": 101}]])
async def test_failed_material_split_leaves_parent_and_children_unchanged(service_db, splits):
    source = await material(service_db)
    batch = await service.create_material_batch(service_db, source.id, 100, operator_id=103)
    await service.perform_iqc(service_db, batch, IQCResult.PASSED, operator_id=103)
    with pytest.raises(ValueError):
        await service.split_batch(service_db, batch, splits, operator_id=103)
    assert batch.current_weight == 100 and batch.status == BatchStatus.AVAILABLE
    assert (await service_db.execute(select(MaterialBatch.id).where(MaterialBatch.parent_batch_id == batch.id))).all() == []


@pytest.mark.asyncio
async def test_negative_material_consumption_cannot_increase_stock(service_db):
    source = await material(service_db)
    batch = await service.create_material_batch(service_db, source.id, 100, operator_id=103)
    await service.perform_iqc(service_db, batch, IQCResult.PASSED, operator_id=103)
    with pytest.raises(ValueError):
        await service.consume_material(service_db, batch, -5, operator_id=103)
    assert batch.current_weight == 100
