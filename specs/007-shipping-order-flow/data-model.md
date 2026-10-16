# Data Model: 发货订单业务流程

## 1. `shipping_orders`

表示业务创建的一张正式订单或样件订单。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `order_no` | string | System-generated, unique |
| `order_type` | enum | `formal` or `sample`; default `formal` |
| `customer_id` | integer nullable | FK to existing customer for formal or existing sample customer |
| `temporary_customer_name` | string nullable | Used only when a sample customer is not in master data |
| `po_no` | string nullable | Required for formal orders; optional for samples; no uniqueness constraint |
| `status` | enum | Derived aggregate status; draft, pending, ready_to_ship, partially_shipped, completed, completed_with_cancellation, cancelled |
| `created_by` | integer | FK to users; draft owner |
| `created_at` | datetime | Required |
| `last_modified_at` | datetime | Drives seven-day draft cleanup |
| `submitted_at` | datetime nullable | Set once on submission |
| `completed_at` | datetime nullable | Set when all lines are shipped or cancelled |

Constraints and indexes:

- Formal order requires `customer_id`, non-empty `po_no`, and at least one valid line at submission time.
- Sample order requires `customer_id` or non-empty `temporary_customer_name`, and does not require `po_no`.
- Do not add a `(customer_id, po_no)` unique constraint; duplicate PO is a warning controlled by the business user.
- Index `status`, `created_by`, `customer_id`, `po_no`, `last_modified_at`, and planned-date lookup through line joins.

## 2. `shipping_order_lines`

表示 PO 中一次计划发货的明细行。同一个 PO 和客户件号可以有多行。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `order_id` | integer | FK to `shipping_orders`, cascade only while draft |
| `part_id` | integer nullable | FK to parts when the physical part is known |
| `part_customer_alias_id` | integer nullable | FK to existing customer-part alias when found |
| `customer_part_no_snapshot` | string | Required, preserves business input |
| `part_name_snapshot` | string | Required at submission; default from part archive, editable per order |
| `ordered_qty` | integer | Positive integer; immutable after submission |
| `planned_ship_date` | date | Required; not earlier than current date at submission |
| `remark` | text nullable | Line note |
| `status` | enum | draft, pending, awaiting_label, ready_to_ship, partially_shipped, shipped, partially_shipped_remaining_cancelled, cancelled |
| `cancelled_qty` | integer | Default 0; cannot exceed ordered minus shipped |
| `created_at` | datetime | Required |
| `updated_at` | datetime | Required |

The service calculates:

```text
shipped_qty = SUM(shipping_shipment_lines.qty for confirmed shipments)
remaining_qty = ordered_qty - shipped_qty - cancelled_qty
```

The database/service transaction rejects negative remaining quantity and any shipment exceeding the current remainder.

## 3. `shipping_label_confirmations`

记录标签人员按明细确认标签。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `order_line_id` | integer | FK to line; one active confirmation per line |
| `confirmed_by` | integer | FK to users |
| `confirmed_at` | datetime | Required |
| `remark` | text nullable | Optional note |

The confirmation is independent of the external label-printing workflow. A line cannot be shipped before a confirmation exists.

## 4. `shipping_cancellation_consents`

记录已标签明细或剩余数量的双人取消确认。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `order_line_id` | integer | FK to line |
| `cancel_qty` | integer | Positive; for a partially shipped line this targets remaining quantity only |
| `reason` | text | Required |
| `business_confirmed_by` | integer nullable | FK to users |
| `business_confirmed_at` | datetime nullable | Set with business confirmation |
| `label_confirmed_by` | integer nullable | FK to users |
| `label_confirmed_at` | datetime nullable | Set with label confirmation |
| `status` | enum | pending, completed, rejected |
| `completed_at` | datetime nullable | Set only after both confirmations |

When both required confirmations exist, one transaction increments the line's `cancelled_qty`, writes an audit event, and recalculates line/PO status.

## 5. `shipping_shipments`

表示一次仓库实际发货。一次 PO 可以有多次发货。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `shipment_no` | string | System-generated, unique |
| `order_id` | integer | FK to order |
| `confirmed_by` | integer | FK to users; warehouse operator |
| `confirmed_at` | datetime | Actual shipment confirmation time |
| `production_batch_no` | string nullable | Reserved for future production traceability; no current validation |
| `remark` | text nullable | Shipment note |

The shipment is created only by explicit warehouse confirmation. Entering logistics information alone does not create a shipment.

## 6. `shipping_shipment_lines`

连接一次发货与订单明细，并记录本次数量。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `shipment_id` | integer | FK to shipment, cascade |
| `order_line_id` | integer | FK to order line |
| `qty` | integer | Positive and no greater than current line remainder |

Indexes should support shipment detail lookup by `order_line_id` and order history lookup by `shipment_id`.

## 7. `shipping_logistics`

一次发货关联的物流明细。支持多个物流号和多个不同物流公司。

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Primary key |
| `shipment_id` | integer | FK to shipment |
| `carrier_name` | string nullable | At least carrier or tracking number is required per shipment confirmation |
| `tracking_no` | string nullable | At least carrier or tracking number is required per shipment confirmation |
| `created_at` | datetime | Required |
| `created_by` | integer | FK to users |

No uniqueness rule is imposed on tracking numbers because carriers and historical corrections may require duplicates; validation and audit remain explicit.

## 8. Existing `audit_logs` integration

Reuse the existing generic audit model with `entity_type` values such as:

- `shipping_order`
- `shipping_order_line`
- `shipping_label_confirmation`
- `shipping_cancellation_consent`
- `shipping_shipment`
- `shipping_logistics`

Actions include create, update, submit, cancel, approve/confirm, delete (draft only), and logistics update. `old_values` and `new_values` are required for logistics edits and other material changes.

## Status derivation

### Line status precedence

1. `draft` while the order is draft.
2. `cancelled` when no quantity shipped and all ordered quantity is cancelled.
3. `shipped` when shipped quantity equals ordered quantity.
4. `partially_shipped_remaining_cancelled` when shipped quantity is positive and remainder is fully cancelled.
5. `partially_shipped` when shipped quantity is positive and remainder remains.
6. `ready_to_ship` when label confirmed and remainder remains.
7. `awaiting_label` when submitted but label is not confirmed.
8. `pending` while formal-order preconditions are still handled.

### Order status aggregation

- `draft`: all lines are still draft.
- `cancelled`: all lines are cancelled and no line has shipped quantity.
- `completed`: all lines are fully shipped.
- `completed_with_cancellation`: every line is fully shipped or cancelled, and at least one line has cancellation.
- `partially_shipped`: at least one line has shipment quantity and another line/remainder remains open.
- `ready_to_ship`: at least one line is ready to ship and no shipment has occurred.
- `pending`: submitted order with no ready-to-ship line yet.
