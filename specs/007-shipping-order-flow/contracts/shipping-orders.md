# Shipping Order API Contract

All endpoints are under the existing API v1 prefix and use the project's bearer authentication and JSON response conventions. Exact URL prefix is inherited from `settings.API_V1_PREFIX`.

## Read and search

### `GET /shipping-orders`

Query filters:

- `customer_id`
- `order_type`: `formal` or `sample`
- `status`
- `po_no`
- `customer_part_no`
- `planned_ship_date_from`, `planned_ship_date_to`
- `created_by`
- pagination fields used by existing list endpoints

Submitted orders are visible to business, label, warehouse, and management users. Drafts are returned only when `created_by` is the current user.

### `GET /shipping-orders/{order_id}`

Returns the order header, lines, derived quantities/statuses, label confirmations, shipment records, logistics rows, production-batch placeholder, warnings, and chronological operation history.

### `GET /shipping-orders/customer-parts/search`

Required query: `customer_id`, `q` (contains match). Returns customer-scoped candidate customer part numbers, linked part name, linked part identifier when available, and any same-physical-part reference hint already present in the part archive. It never selects a candidate automatically.

## Draft and submission

### `POST /shipping-orders`

Creates a draft. The default `order_type` is `formal`. Draft payload may be incomplete.

```json
{
  "order_type": "formal",
  "customer_id": 12,
  "temporary_customer_name": null,
  "po_no": "WX-20260822-018",
  "lines": [
    {
      "customer_part_no": "60015399",
      "part_id": 42,
      "part_customer_alias_id": 77,
      "part_name": "业务确认名称",
      "ordered_qty": 600,
      "planned_ship_date": "2026-09-01",
      "remark": "首批"
    }
  ]
}
```

### `PATCH /shipping-orders/{order_id}`

Updates a draft only and only for its creator. Submitted orders are rejected. Each successful update refreshes `last_modified_at`.

### `POST /shipping-orders/{order_id}/submit`

Validates required fields and freezes order lines. The client must explicitly confirm warnings:

```json
{
  "confirm_duplicate_po": false,
  "confirm_unregistered_customer_parts": false
}
```

If a warning exists and its confirmation is false, return a structured `409` response:

```json
{
  "code": "UNREGISTERED_CUSTOMER_PARTS",
  "message": "该客户件号在零件档案中找不到，请确认是否继续提交。",
  "details": [{"line_id": 11, "customer_part_no": "60015399"}]
}
```

Duplicate PO uses `DUPLICATE_CUSTOMER_PO` and includes existing order number, status, and creation time. The server never merges or blocks after explicit confirmation.

### `POST /shipping-orders/{order_id}/withdraw`

Withdraws an untagged submitted order/line to draft according to the spec. Tagged lines cannot use this endpoint. The action is audited.

## Label and cancellation

### `POST /shipping-order-lines/{line_id}/label-confirm`

Confirms one line by a label operator. The line becomes `ready_to_ship`; other lines are unaffected. Sample orders use this endpoint after offline picking.

### `POST /shipping-order-lines/{line_id}/cancel`

Cancels an untagged line directly, or creates/completes the appropriate consent flow for a tagged line. The request includes `cancel_qty` and a required reason.

### `POST /shipping-order-lines/{line_id}/cancellation-consent`

Records the current actor's business or label confirmation. The server infers the actor identity and role from authentication, rejects duplicate confirmation by the same actor, and completes cancellation only once both required confirmations exist.

## Shipment

### `POST /shipping-orders/{order_id}/shipments/confirm`

Confirms one or more shipment lines. The request supports line-level and whole-order UI actions, but the server always processes explicit line quantities:

```json
{
  "lines": [
    {"order_line_id": 11, "qty": 600},
    {"order_line_id": 12, "qty": 100}
  ],
  "logistics": [
    {"carrier_name": "顺丰", "tracking_no": "SF123"},
    {"carrier_name": "京东物流", "tracking_no": "JD456"}
  ],
  "remark": "首批发货",
  "production_batch_no": null
}
```

Rules:

- Every line must be label-confirmed before shipment.
- Each quantity must be positive and no greater than current remainder.
- At least one carrier or tracking number is required across the logistics rows.
- The shipment, shipment lines, logistics rows, inventory reference hook, line statuses, order status, and audit event are committed transactionally.
- Existing unregistered customer-part warnings are shown again before the warehouse confirmation is finalized.

### `PATCH /shipping-shipments/{shipment_id}/logistics`

Adds or edits logistics rows after shipment confirmation. It never changes shipment quantity or status. The response includes the new row and the audit record containing old/new values, operator, and time.

### `GET /shipping-orders/{order_id}/history`

Returns chronological audit events for the order, its lines, label confirmations, cancellation consents, shipments, and logistics edits.

## Error codes

- `DRAFT_NOT_VISIBLE`: current user is not the creator of a draft.
- `DRAFT_NOT_EDITABLE`: order is already submitted.
- `DUPLICATE_CUSTOMER_PO`: duplicate customer + PO warning.
- `UNREGISTERED_CUSTOMER_PARTS`: one or more customer part numbers are not in the part archive.
- `INVALID_PLANNED_DATE`: planned date is earlier than today.
- `INVALID_SHIPMENT_QTY`: quantity is non-positive or exceeds remainder.
- `LINE_NOT_READY_TO_SHIP`: label confirmation is missing.
- `CANCELLATION_CONSENT_REQUIRED`: tagged line needs both actors.
- `LOGISTICS_REQUIRED`: neither carrier nor tracking number was supplied.
