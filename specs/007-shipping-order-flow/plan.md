# Implementation Plan: 发货订单业务流程

**Branch**: `007-shipping-order-flow` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

## Summary

在现有 Zephyr ERP 中新增发货订单域，覆盖正式订单、样件订单、订单明细、标签确认、撤回/取消、分批发货、物流信息和操作历史。设计参考 ERPNext 的 `Sales Order -> Pick List -> Delivery Note` 分层，以及 Odoo 的订单明细、库存移动和部分出库模型，但不引入整套 ERP 框架或复制外部项目代码。

实施采用现有 FastAPI + SQLAlchemy 异步模型 + Alembic + Vue 3/Element Plus 架构。订单明细保存客户件号和零件名称快照，发货记录作为数量事实来源；每次部分发货独立记录物流信息，草稿由后台维护任务按最后修改时间清理。

## Technical Context

**Language/Version**: Python 3.11+; TypeScript/Vue 3

**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Pydantic, Vue 3, Element Plus, Axios

**Storage**: PostgreSQL through the existing async SQLAlchemy session and Alembic migrations

**Testing**: pytest for service/API/database behavior; Playwright for real browser acceptance; existing frontend type-check/build commands

**Target Platform**: Existing Zephyr ERP web application and its current server deployment

**Project Type**: Full-stack web application

**Performance Goals**: Customer-part search results visible within 1 second for normal interactive use; order detail and shipment history usable without pagination delays for typical PO sizes; shipment confirmation completes as one database transaction

**Constraints**: Preserve existing customer, part alias, packaging/inventory, user permission, and audit conventions. Do not expose secrets. Do not physically delete submitted, shipped, or cancelled business records. Draft cleanup must target only drafts older than seven days by `last_modified_at`.

**Scale/Scope**: Small manufacturing ERP workflow for multiple business, label, warehouse, and management users; a PO may contain many lines, repeated customer part numbers, and many shipment records.

## Constitution Check

The repository does not currently contain `specs/constitution.md` or `.specify/memory/constitution.md`. The project-level governance source available for this work is `AGENTS.md`, which requires staged implementation, independent acceptance evidence, secret protection, and real browser testing for user-visible changes.

### Gates

- Pass: scope is limited to the documented shipping-order workflow and its supporting contracts.
- Pass: implementation will reuse existing project patterns rather than introducing a replacement ERP framework.
- Pass: database mutations will use migrations and transactional service operations.
- Pass: all user-visible frontend stages will include browser acceptance; API/build checks alone will not be treated as acceptance.
- Pass: draft cleanup will use an exact status/time predicate and will be tested before enabling scheduled execution.

## Architecture and Design

### Domain boundaries

1. **Order domain** owns order type, customer/temporary customer, PO number, draft ownership, order lines, status aggregation, and submission warnings.
2. **Label gate** owns line-level label confirmation and the two-party cancellation consent required after label confirmation.
3. **Shipment domain** owns partial shipment quantities, shipment records, logistics rows, production-batch placeholder, and shipment history.
4. **Existing domains** remain authoritative for customers, customer part aliases, parts, packaging records, finished-goods inventory, and generic audit logs. Inventory allocation and QR assignment remain deferred integrations.

### Authoritative quantity rules

- `ordered_qty` is the immutable submitted quantity for a line.
- Confirmed shipment-line quantities are the authoritative shipped quantity.
- A cancellation record is the authoritative cancelled remainder quantity.
- `remaining_qty = ordered_qty - shipped_qty - cancelled_qty`; the service rejects negative or over-shipment results.
- Line and PO statuses are derived from label state, shipped quantity, cancelled quantity, and remaining quantity rather than being edited directly by the client.

### State handling

- Draft lines are editable only by the order creator.
- Submission freezes line business fields.
- Untagged lines may be withdrawn to draft or directly cancelled by the creator/business actor according to the spec.
- Tagged lines cannot return to draft. Cancellation requires both business and label confirmation; the confirmation transaction records both actors and the reason.
- Sample orders skip full inspection and system picking, but still require label confirmation before warehouse shipment.
- A warehouse shipment confirmation is the only action that changes shipment quantities; logistics-only edits never change shipment status.

## Project Structure

### Documentation (this feature)

```text
specs/007-shipping-order-flow/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── contracts/shipping-orders.md
```

### Backend

```text
backend/app/models/shipping_order.py
backend/app/schemas/shipping_order.py
backend/app/services/shipping_order_service.py
backend/app/api/shipping_orders.py
backend/app/models/__init__.py
backend/app/schemas/__init__.py
backend/app/services/__init__.py
backend/app/main.py
alembic/versions/<revision>_shipping_orders.py
scripts/cleanup_shipping_drafts.py
```

### Frontend

```text
frontend/src/views/shipping-orders/index.vue
frontend/src/views/shipping-orders/detail.vue
frontend/src/components/shipping-orders/OrderLineEditor.vue
frontend/src/components/shipping-orders/ShipmentConfirmDialog.vue
frontend/src/components/shipping-orders/OperationHistory.vue
frontend/src/router/index.ts
frontend/src/locales/zh-CN.ts
```

### Tests

```text
backend/tests/test_shipping_order_service.py
backend/tests/api/test_shipping_orders.py
backend/tests/test_shipping_order_states.py
tests/playwright/test-shipping-orders.js
frontend/src/tests/shipping-orders.spec.ts
```

**Structure Decision**: Extend the existing backend/frontend monorepo in the same model-service-API-view pattern. The feature gets one bounded backend domain and one bounded frontend workspace; it does not create a new application or import an external ERP runtime.

## Implementation Phases

### Phase 0 - Research and decisions

- Record GitHub comparison and reuse decision in `research.md`.
- Freeze the distinction between order lines, label confirmations, shipment records, and logistics rows.
- Confirm that existing `PartCustomerAlias` supplies customer-scoped search and that `AuditLog` supplies generic history storage.
- Document deferred inventory and QR integrations so they do not leak into the first migration.

### Phase 1 - Data model and contracts

- Add the shipping-order tables and indexes described in `data-model.md`.
- Use nullable part/alias references with non-null snapshots for customer part number and display name so an unregistered part number can be submitted after warning.
- Add the line-level label confirmation and two-party cancellation-consent records.
- Add shipment, shipment-line, and shipment-logistics records with production-batch placeholder.
- Add transactional constraints and service-level checks for quantities, dates, duplicate PO warnings, and logistics minimums.
- Publish API contracts and warning codes in `contracts/shipping-orders.md`.

### Phase 2 - Backend workflow

- Implement draft create/update/delete with creator-only visibility and seven-day cleanup command.
- Implement customer-part contains search scoped to selected customer, including candidate display for Tab/dropdown completion.
- Implement submit flow with duplicate PO and unregistered customer-part warnings that require explicit client confirmation.
- Implement sample-order submission path without full-inspection or system-picking side effects.
- Implement line label confirmation, withdrawal, direct cancellation, and two-party cancellation completion.
- Implement line-level and whole-order shipment confirmation with partial quantities, multiple logistics rows, and transaction-safe status aggregation.
- Implement logistics add/update history and order detail operation history.

### Phase 3 - Frontend workflow

- Build order list with role-appropriate default filters while keeping one shared submitted-order view.
- Build draft editor with formal/sample toggle, customer/temporary-customer handling, customer-part search, Tab/dropdown selection, editable name snapshot, repeated lines, dates, quantities, and notes.
- Build warning dialogs for duplicate PO and unregistered customer parts.
- Build submitted-order detail with line statuses, label confirmation controls, cancellation consent controls, shipment records, logistics rows, and operation history.
- Build warehouse shipment confirmation for line-level and whole-order actions; prevent shipment quantity overrun in the UI while retaining server validation.

### Phase 4 - Verification and rollout

- Run migration validation against a disposable database and verify indexes/constraints.
- Run backend unit, service, API, and state-transition tests.
- Run frontend type-check/build and Playwright browser acceptance for formal orders, sample orders, repeated lines, warnings, label confirmation, two-party cancellation, partial shipments, multiple logistics, and history.
- Run the seven-day cleanup in dry-run mode, verify only eligible drafts are selected, then document the deployment scheduler/Task Scheduler invocation.
- Update the feature acceptance report with implementation and browser acceptance results separately.

## Risks and Mitigations

- **External ERP mismatch**: use ERPNext/Odoo only as domain references; keep the Zephyr data model and UI conventions authoritative.
- **Unknown customer part later enters production flow**: store raw snapshots and warning history now; defer inventory/QR resolution rules to the dedicated follow-up spec.
- **Quantity race conditions**: lock or transactionally re-check the line's current shipped/cancelled totals during shipment confirmation.
- **Dual confirmation ambiguity**: store each actor's confirmation separately and finalize cancellation only when both required confirmations exist.
- **Draft cleanup loss**: run an auditable dry-run, filter strictly by `status=draft` and `last_modified_at < now-7d`, and never delete submitted data.

## Complexity Tracking

No constitution violations or unnecessary new projects are introduced. The feature adds one bounded domain to the existing application and one maintenance command because the current repository has no general scheduler suitable for draft retention.
