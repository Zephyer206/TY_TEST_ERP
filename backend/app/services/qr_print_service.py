"""Persist print-data issuance separately from operator-confirmed printing."""
from __future__ import annotations

import asyncio
import base64
import io

import qrcode
from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit import AuditAction
from app.models import product_box as m
from app.services import product_box_service as boxes, qr_permission_service as permissions
from app.services.qr_transaction_service import (
    QrError, advisory_lock, lock_rows, transactional_write, write_audit,
)

TEMPLATE = {"code": "a4_3x7_v1", "paper_width_mm": 210, "paper_height_mm": 297,
            "margin_mm": 10, "columns": 3, "rows": 7, "label_width_mm": 60,
            "label_height_mm": 35, "gap_mm": 5, "quiet_zone_modules": 4}


def validate_ids(identifiers):
    if (not identifiers or len(identifiers) > settings.PRODUCT_QR_BATCH_LIMIT
            or len(set(identifiers)) != len(identifiers)
            or any(isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in identifiers)):
        raise QrError(400, "INVALID_QUANTITY", "请选择允许数量范围内的不重复二维码")


def render_labels(snapshots):
    labels = []
    for snapshot in snapshots:
        # Native integer modules and four-module quiet zone: no smoothed resize.
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=4)
        qr.add_data(snapshot["qr_payload"])
        qr.make(fit=True)
        stream = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(stream, format="PNG")
        labels.append(snapshot | {"qr_image_base64": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")})
    return labels


async def visible_items(db, actor, item_ids):
    scope = await boxes.pool_scope(db, actor)
    rows = (await db.execute(select(m.ProductQrPoolItem, m.ProductBox)
        .outerjoin(m.ProductBox, m.ProductBox.qr_pool_item_id == m.ProductQrPoolItem.id)
        .where(m.ProductQrPoolItem.id.in_(item_ids), scope).order_by(m.ProductQrPoolItem.id))).all()
    if len(rows) != len(item_ids):
        raise QrError(404, "ENTITY_NOT_FOUND", "部分二维码不存在或当前账号不可见")
    return rows


async def create_job(db, actor, item_ids, template_code, request_type):
    # The actor's live permission is checked before both initial execution and
    # replay. Snapshots contain only this user's currently visible fields.
    rows = await visible_items(db, actor, item_ids)
    await lock_rows(db, pool=item_ids)
    job = m.QrPrintJob(requested_by=actor.id, template_code=template_code, request_type=request_type)
    db.add(job)
    await db.flush()
    snapshots = []
    for item, box in rows:
        snapshot = boxes.pool_info(item, box.id if box else None)
        if box:
            snapshot["box"] = boxes.box_info(box, item)
        snapshots.append(snapshot)
        db.add(m.QrPrintJobItem(job_id=job.id, pool_item_id=item.id, display_snapshot=snapshot))
    labels = await asyncio.to_thread(render_labels, snapshots)
    await write_audit(db, actor.id, AuditAction.EXPORT, f"print-job:{job.id}",
                      after={"item_ids": [str(i) for i in sorted(item_ids)], "request_type": request_type})
    return {"print_job_id": str(job.id), "template": TEMPLATE, "items": labels}


async def print_data(db, actor, *, item_ids, idempotency_key, template_code="a4_3x7_v1"):
    await permissions.require_action(db, actor, "print", lock=True)
    validate_ids(item_ids)
    if template_code != TEMPLATE["code"]:
        raise QrError(400, "INVALID_TEMPLATE", "该打印模板尚未启用")
    await visible_items(db, actor, item_ids)
    return await transactional_write(db, actor.id, "print-data", "pool", idempotency_key,
        {"item_ids": [str(i) for i in sorted(item_ids)], "template_code": template_code},
        lambda: create_job(db, actor, item_ids, template_code, "initial"), http_status=201)


async def reprint(db, actor, *, item_id, idempotency_key, template_code="a4_3x7_v1"):
    await permissions.require_action(db, actor, "print", lock=True)
    validate_ids([item_id])
    if template_code != TEMPLATE["code"]:
        raise QrError(400, "INVALID_TEMPLATE", "该打印模板尚未启用")
    await visible_items(db, actor, [item_id])
    return await transactional_write(db, actor.id, "reprint", f"pool:{item_id}", idempotency_key,
        {"item_id": str(item_id), "template_code": template_code},
        lambda: create_job(db, actor, [item_id], template_code, "reprint"), http_status=201)


async def confirm_print(db, actor, *, print_job_id, confirmed_item_ids, idempotency_key):
    await permissions.require_action(db, actor, "print", lock=True)
    validate_ids(confirmed_item_ids)
    job = await db.get(m.QrPrintJob, print_job_id)
    if job is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "打印作业不存在")
    if job.requested_by != actor.id:
        raise QrError(403, "FORBIDDEN", "只有作业申请人可以确认已打印")
    await visible_items(db, actor, confirmed_item_ids)

    async def operation():
        await advisory_lock(db, "qr-print-job", print_job_id)
        members = set((await db.execute(select(m.QrPrintJobItem.pool_item_id).where(
            m.QrPrintJobItem.job_id == print_job_id))).scalars())
        if not set(confirmed_item_ids) <= members:
            raise QrError(400, "INVALID_QUANTITY", "确认项目必须属于该打印作业")
        rows = (await lock_rows(db, pool=confirmed_item_ids))["pool"]
        already = set((await db.execute(select(m.QrPrintConfirmation.pool_item_id).where(
            m.QrPrintConfirmation.job_id == print_job_id,
            m.QrPrintConfirmation.pool_item_id.in_(confirmed_item_ids)))).scalars())
        now = await db.scalar(select(func.clock_timestamp()))
        bound_boxes = dict((await db.execute(select(m.ProductBox.qr_pool_item_id, m.ProductBox.id).where(
            m.ProductBox.qr_pool_item_id.in_(confirmed_item_ids)))).all())
        for identity in sorted(set(confirmed_item_ids) - already):
            item = rows[identity]
            db.add(m.QrPrintConfirmation(job_id=print_job_id, pool_item_id=identity,
                                       confirmed_by=actor.id, confirmed_at=now))
            item.print_count += 1
            if item.printed_at is None:
                item.printed_at = now
            item.updated_at = now
        await write_audit(db, actor.id, AuditAction.UPDATE, f"print-confirmation:{print_job_id}",
                          after={"new_confirmed_item_ids": [str(i) for i in sorted(set(confirmed_item_ids) - already)]})
        return {"print_job_id": str(print_job_id),
                "items": [boxes.pool_info(rows[i], bound_boxes.get(i)) for i in sorted(confirmed_item_ids)]}

    return await transactional_write(db, actor.id, "print-confirm", f"job:{print_job_id}", idempotency_key,
        {"print_job_id": str(print_job_id), "confirmed_item_ids": [str(i) for i in sorted(confirmed_item_ids)]}, operation)
