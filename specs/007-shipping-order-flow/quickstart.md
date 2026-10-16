# Quickstart: 发货订单流程实施验证

This document describes the verification flow after implementation. It does not contain credentials or environment secrets.

## 1. Prepare a test database

Use the project's existing test database configuration and run the new migration through the normal Alembic workflow. Do not run the cleanup command against production data during development.

Expected result:

- All shipping-order tables and indexes exist.
- Existing customer, part alias, packaging, inventory, and audit tables remain intact.

## 2. Backend checks

Run the focused tests:

```powershell
pytest backend/tests/test_shipping_order_states.py backend/tests/test_shipping_order_service.py backend/tests/api/test_shipping_orders.py
```

The focused suite must cover:

- formal order default and required PO;
- sample order with temporary customer and no PO;
- repeated customer part lines in one PO;
- contains search, dropdown/Tab candidate behavior, and no auto-selection;
- duplicate PO warning and explicit continuation;
- unregistered customer-part warning at submit and shipment;
- creator-only draft visibility and edit/delete;
- seven-day cleanup by last modified time;
- label confirmation and untagged withdrawal;
- two-party cancellation after label confirmation;
- partial shipment quantity arithmetic;
- multiple carriers/tracking numbers;
- logistics correction audit;
- order aggregate status transitions.

## 3. Frontend acceptance flow

Start the existing backend and frontend development services, then use a controllable browser session to verify the actual UI:

1. Sign in as a business user and create a formal draft with two lines for the same customer part but different dates.
2. Confirm customer-part search is scoped to the selected customer, supports contains matching, and requires dropdown/Tab selection.
3. Submit with a duplicate PO or unregistered customer part and verify the warning dialog; continue only after explicit confirmation.
4. Confirm another user cannot see the creator's draft, then verify submitted orders are visible to business, label, warehouse, and management roles.
5. As label personnel, confirm one line and verify only that line becomes ready to ship.
6. As warehouse personnel, ship part of the line with two logistics rows from different carriers.
7. Ship the remainder with another carrier and verify independent shipment history and correct aggregate status.
8. Edit logistics after shipment and verify old/new values in operation history.
9. Test sample order: no PO, temporary customer, no full-inspection task, offline-pick label confirmation, then warehouse shipment.

The browser acceptance report must identify the browser session and observed behavior separately from backend test results, per `AGENTS.md`.

## 4. Draft cleanup verification

Run the cleanup command in dry-run mode first:

```powershell
python scripts/cleanup_shipping_drafts.py --dry-run
```

Verify that only records with `status=draft` and `last_modified_at` older than seven days are selected. Then run the command in a disposable test database and verify submitted, shipped, and cancelled records remain.

## 5. Deferred acceptance

Do not mark the following as complete in this feature:

- automatic finished-goods allocation or reservation;
- QR-driven inspection task assignment;
- label template/printing implementation;
- production batch validation;
- returns or shipment reversal.
