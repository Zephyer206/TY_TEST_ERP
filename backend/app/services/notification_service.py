"""Durable in-app delivery; transport outcomes never decide business exceptions."""
from datetime import timedelta

from sqlalchemy import exists, func, select

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.part import Part
from app.models.user import User
from app.services import product_box_service as boxes, qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_permission_users, transactional_write, write_audit

BACKOFF_MINUTES = (1, 5, 15, 30)


async def resolve_recipient_groups(db, item):
    supervisors = list((await db.scalars(select(User.id).join(m.QrCapabilityGrant,
        m.QrCapabilityGrant.user_id == User.id).where(User.dept == "prod", User.role_level >= 2,
        m.QrCapabilityGrant.capability == "qr.supervise", m.QrCapabilityGrant.revoked_at.is_(None))
        .order_by(User.id))).all())
    context = await db.scalar(select(m.ProductOrderContext).where(m.ProductOrderContext.order_id == item.order_id))
    owner = await db.get(User, context.business_owner_id) if context and context.business_owner_id else None
    owners = [owner.id] if owner and owner.dept == "sales" and owner.role_level >= 2 else []
    state = await db.get(m.MachineOrderProcessState, item.state_id)
    product = await db.get(m.ProductOrderProduct, state.order_product_id)
    part = await db.get(Part, product.part_id)
    now = await db.scalar(select(func.clock_timestamp()))
    for kind, recipients in (("supervisor", supervisors), ("business_owner", owners)):
        group = await db.scalar(select(m.ExceptionRecipientGroup).where(m.ExceptionRecipientGroup.exception_id == item.id,
            m.ExceptionRecipientGroup.group_type == kind).with_for_update())
        if group is None:
            group = m.ExceptionRecipientGroup(exception_id=item.id, group_type=kind)
            db.add(group)
        if group.resolution_status == "resolved":
            continue
        group.recipient_ids = recipients
        group.resolution_status = "resolved" if recipients else "pending_configuration"
        group.resolved_at = now if recipients else None
        group.missing_reason = None if recipients else f"MISSING_{kind.upper()}"
        for identity in recipients:
            key = f"coil:{item.id}:recipient:{identity}:inapp"
            if await db.scalar(select(m.NotificationOutbox.id).where(m.NotificationOutbox.dedupe_key == key)) is None:
                db.add(m.NotificationOutbox(dedupe_key=key, recipient_user_id=identity, exception_id=item.id,
                    event_type="coil_spec_exception", payload_json={"kind": "coil_spec_exception", "exception_id": str(item.id),
                        "order_id": item.order_id, "plan_no": f"PP-{item.order_id:06d}",
                        "process_code": state.process_code, "product_name": part.internal_name if part else None}))
        await db.flush()


async def backfill_recipients(db, limit=100):
    missing = exists(select(m.ExceptionRecipientGroup.id).where(m.ExceptionRecipientGroup.exception_id == m.CoilSpecException.id,
        m.ExceptionRecipientGroup.resolution_status == "pending_configuration"))
    rows = (await db.scalars(select(m.CoilSpecException).where(missing).order_by(m.CoilSpecException.id)
        .limit(limit).with_for_update(skip_locked=True))).all()
    for item in rows:
        await resolve_recipient_groups(db, item)
    return len(rows)


async def persist_inapp(db, outbox):
    if await db.scalar(select(m.QrNotification.id).where(m.QrNotification.outbox_id == outbox.id)) is None:
        db.add(m.QrNotification(outbox_id=outbox.id, recipient_user_id=outbox.recipient_user_id, payload_json=outbox.payload_json))
    await db.flush()


async def dispatch_due(db, *, limit=100, now=None, sink=None):
    now = now or await db.scalar(select(func.clock_timestamp()))
    sink = sink or persist_inapp
    candidates = list((await db.scalars(select(m.NotificationOutbox.recipient_user_id).where(
        m.NotificationOutbox.status == "pending", m.NotificationOutbox.next_retry_at <= now,
        m.NotificationOutbox.attempts < 5).order_by(m.NotificationOutbox.id).limit(limit))).all())
    # Revocation and delivery serialize before acquiring outbox rows.
    await lock_permission_users(db, *candidates)
    rows = (await db.scalars(select(m.NotificationOutbox).where(m.NotificationOutbox.status == "pending",
        m.NotificationOutbox.next_retry_at <= now, m.NotificationOutbox.attempts < 5,
        m.NotificationOutbox.recipient_user_id.in_(candidates)).order_by(m.NotificationOutbox.id)
        .limit(limit).with_for_update(skip_locked=True).execution_options(populate_existing=True))).all()
    summary = {"processed": 0, "sent": 0, "failed_attempts": 0}
    from app.services.coil_exception_service import can_decide
    for row in rows:
        actor = await db.get(User, row.recipient_user_id, populate_existing=True)
        item = await db.get(m.CoilSpecException, row.exception_id)
        safe_error = None
        if actor is None or not await can_decide(db, actor, item.order_id):
            safe_error = "RECIPIENT_NO_LONGER_AUTHORIZED"
        else:
            try:
                async with db.begin_nested():
                    await sink(db, row)
                    # A transport callback is not enough: the durable task must exist.
                    if await db.scalar(select(m.QrNotification.id).where(m.QrNotification.outbox_id == row.id)) is None:
                        raise RuntimeError("In-app task was not persisted")
            except Exception:
                safe_error = "INAPP_DELIVERY_FAILED"
        row.attempts += 1
        row.version += 1
        row.last_error = safe_error
        if safe_error:
            row.status = "failed" if row.attempts == 5 else "pending"
            if row.attempts < 5:
                row.next_retry_at = now + timedelta(minutes=BACKOFF_MINUTES[row.attempts - 1])
            summary["failed_attempts"] += 1
        else:
            row.status, row.sent_at = "sent", now
            summary["sent"] += 1
        db.add(m.QrNotificationAttempt(outbox_id=row.id, retry_batch=row.retry_batch, attempt_no=row.attempts,
            trigger_type="manual" if row.retry_batch > 0 and row.attempts == 1 else "automatic",
            result="failed" if safe_error else "sent", safe_error_code=safe_error, created_at=now))
        summary["processed"] += 1
        await db.flush()
    return summary


async def delivery_info(db, actor, row, *, include_attempts=False):
    from app.services.coil_exception_service import exception_info
    item = await db.get(m.CoilSpecException, row.exception_id)
    task = await db.scalar(select(m.QrNotification).where(m.QrNotification.outbox_id == row.id))
    result = {"id": str(row.id), "recipient_user_id": row.recipient_user_id, "delivery_status": row.status,
        "attempts": row.attempts, "retry_batch": row.retry_batch, "version": row.version,
        "next_retry_at": boxes.iso(row.next_retry_at), "last_error": row.last_error,
        "sent_at": boxes.iso(row.sent_at), "created_at": boxes.iso(row.created_at),
        "notification_id": str(task.id) if task else None, "read_at": boxes.iso(task.read_at) if task else None,
        "exception": await exception_info(db, actor, item)}
    if include_attempts:
        attempts = (await db.scalars(select(m.QrNotificationAttempt).where(m.QrNotificationAttempt.outbox_id == row.id)
            .order_by(m.QrNotificationAttempt.id))).all()
        result["attempt_history"] = [{"retry_batch": a.retry_batch, "attempt_no": a.attempt_no,
            "trigger_type": a.trigger_type, "result": a.result, "safe_error_code": a.safe_error_code,
            "created_at": boxes.iso(a.created_at)} for a in attempts]
    return result


async def list_notifications(db, actor, *, delivery_status=None, unread_only=False, page=1, page_size=25):
    permissions.validate_actor(actor)
    scope = await permissions.visible_order_clause(db, actor, m.CoilSpecException.order_id)
    query = select(m.NotificationOutbox).join(m.CoilSpecException, m.CoilSpecException.id == m.NotificationOutbox.exception_id
        ).outerjoin(m.QrNotification, m.QrNotification.outbox_id == m.NotificationOutbox.id).where(
            m.NotificationOutbox.recipient_user_id == actor.id, scope)
    if delivery_status:
        query = query.where(m.NotificationOutbox.status == delivery_status)
    if unread_only:
        query = query.where(m.QrNotification.id.is_not(None), m.QrNotification.read_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.scalars(query.order_by(m.NotificationOutbox.id.desc()).offset((page-1)*page_size).limit(page_size))).all()
    caps = await permissions.capabilities(db, actor)
    return {"items": [await delivery_info(db, actor, row) for row in rows], "total": total, "page": page, "page_size": page_size,
        "can_manage_deliveries": actor.role_level == 4 and "qr.admin" in caps}


async def list_deliveries(db, actor, *, delivery_status=None, page=1, page_size=25):
    await permissions.require_action(db, actor, "admin")
    query = select(m.NotificationOutbox)
    if delivery_status:
        query = query.where(m.NotificationOutbox.status == delivery_status)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.scalars(query.order_by(m.NotificationOutbox.id.desc()).offset((page-1)*page_size).limit(page_size))).all()
    return {"items": [await delivery_info(db, actor, row, include_attempts=True) for row in rows], "total": total,
        "page": page, "page_size": page_size, "can_manage_deliveries": True}


async def retry_delivery(db, actor, *, delivery_id, expected_version, idempotency_key):
    await permissions.require_action(db, actor, "admin", lock=True)

    async def operation():
        row = await db.scalar(select(m.NotificationOutbox).where(m.NotificationOutbox.id == delivery_id)
            .with_for_update().execution_options(populate_existing=True))
        if row is None:
            raise QrError(404, "ENTITY_NOT_FOUND", "通知投递不存在")
        check_version(row.version, expected_version, code="STATE_CONFLICT")
        if row.status != "failed":
            raise QrError(409, "STATE_CONFLICT", "仅失败队列可建立新的人工重试批次")
        before = {"status": row.status, "retry_batch": row.retry_batch, "attempts": row.attempts}
        row.retry_batch, row.attempts, row.version = row.retry_batch + 1, 0, row.version + 1
        row.status, row.sent_at, row.last_error = "pending", None, None
        row.next_retry_at = await db.scalar(select(func.clock_timestamp()))
        await db.flush()
        result = await delivery_info(db, actor, row, include_attempts=True)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"notification-retry:{row.id}", before=before, after=result)
        return result
    return await transactional_write(db, actor.id, "delivery-retry", f"delivery:{delivery_id}", idempotency_key,
        dict(expected_version=expected_version), operation)
