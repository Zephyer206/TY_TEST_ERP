# Quickstart: Material QR Traceability — MVP Verification

**验证场景**：US1（原料进厂赋码）+ US2（大卷分条衍生）
**验收标准**：SC-001 ~ SC-003

> 前置条件：数据库迁移 `qr002_material_traceability` 已执行，`alembic upgrade qr002_material_traceability`

---

## 场景一：原料入库赋码

**验收标准**：原料到厂到二维码标签打印张贴 ≤ 5 分钟（SC-001）

### 步骤 1：创建物料目录（如尚未创建）

```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/materials" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "name": "冷轧钢带",
    "grade": "DC01",
    "thickness": 0.8,
    "width": 1250,
    "unit": "kg"
  }'
```

响应包含 `material_no`（如 `MAT-20260613-093012`），记录 `id`。

### 步骤 2：登记原料批次（入库即赋码）

```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "material_id": <MATERIAL_ID>,
    "gross_weight": 5000,
    "thickness": 0.8,
    "width": 1250,
    "length": 2000
  }'
```

**验证**：响应中 `qr_code` 字段非空，格式为 `MAT:{id}:{YYYYMMDD}`。
记录返回的 `id` 和 `batch_no`。

### 步骤 3：扫码查询台账

```bash
curl "http://localhost:8000/api/v1/warehouse/material-batches/scan/<BATCH_ID>" \
  -H "Authorization: Bearer <TOKEN>"
```

**验证**：响应包含：
- `qr_code`、`qr_image_base64`（可打印二维码）
- `material_name`、`material_grade`（牌号）
- `supplier_name`、`status`
- `gross_weight`、`current_weight`
- `received_at`

### 步骤 4：查询流转记录

```bash
curl "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/trace" \
  -H "Authorization: Bearer <TOKEN>"
```

**验证**：返回 `transactions` 列表，第一条为 `iqc` 记录（若已完成 IQC）。

---

## 场景二：大卷分条小卷

**验收标准**：分条完成后，子卷二维码在 2 分钟内可打印（SC-003）

### 步骤 1：执行 IQC（通过）

```bash
curl -X PUT "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/iqc" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"result": "passed"}'
```

**验证**：`status` 变为 `available`。

### 步骤 2：分条操作（扫码母卷）

```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/split" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "splits": [
      {"width": 400, "weight": 1600},
      {"width": 400, "weight": 1600},
      {"width": 450, "weight": 1500}
    ]
  }'
```

**验证**：
- 响应 3 个子卷，每个有独立 `qr_code`（`MAT:{child_id}:{date}`）
- 每个有 `qr_image_base64`（可打印）
- 母卷 `status` 变为 `PARTIAL`
- 母卷 `current_weight` 已扣减

### 步骤 3：扫码子卷（横向追溯）

```bash
# 获取子卷 ID（从步骤2响应中取 child_id）
curl "http://localhost:8000/api/v1/warehouse/material-batches/scan/child/<CHILD_ID>" \
  -H "Authorization: Bearer <TOKEN>"
```

**验证**：
- `child_batch`：子卷台账（独立 batch_no、独立 qr_code）
- `parent_batch`：母卷完整信息（batch_no、status=PARTIAL）
- `sibling_batches`：同胞子卷列表（其他 2 个子卷的信息）

### 步骤 4：扫码母卷查子卷列表

```bash
curl "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/children" \
  -H "Authorization: Bearer <TOKEN>"
```

**验证**：返回母卷下所有 3 个子卷的列表（含 qr_code、status、weight）。

---

## 场景三：扫码日志验证

```bash
# 查询母卷扫码历史
curl "http://localhost:8000/api/v1/warehouse/scans/MAT/<BATCH_ID>" \
  -H "Authorization: Bearer <TOKEN>"
```

**验证**：
- 存在 `query` 记录（扫码台账）
- 存在 `split` 记录（分条操作）
- 每条记录含 `operator_id`、`scanned_at`

---

## 场景四：二维码损毁补打（边界情况）

```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/reprint-qr"
```

**验证**（T026 待实现）：返回 qr_code 和 qr_image_base64。

---

## 场景五：反向追溯验证（可选）

通过子卷 ID 查询追溯链：

```bash
curl "http://localhost:8000/api/v1/warehouse/material-batches/scan/child/<CHILD_ID>" \
  -H "Authorization: Bearer <TOKEN>"
```

结合流转记录，可完整还原：子卷 → 母卷 → 入库记录 → 供应商。

---

## 依赖的 API 端点（按任务编号）

| 任务 | 方法 | 端点 | 说明 |
|------|------|------|------|
| T011 | POST | `/warehouse/material-batches` | 登记入库（自动赋码） |
| T012 | GET | `/warehouse/material-batches/scan/{id}` | 扫码台账 |
| T013 | GET | `/warehouse/material-batches/{id}/trace` | 流转记录 |
| T015 | POST | `/warehouse/material-batches/{id}/split` | 分条（返回子卷 QR） |
| T016 | GET | `/warehouse/material-batches/scan/child/{id}` | 扫码子卷+横向追溯 |
| T017 | GET | `/warehouse/material-batches/{id}/children` | 母卷查子卷列表 |
| T006 | POST | `/warehouse/scans` | 记录扫码日志 |
| T007 | GET | `/warehouse/scans/{type}/{id}` | 查询扫码历史 |
| T008 | GET | `/warehouse/material-batches/{id}` | 母卷详情（内含 IQC 状态） |
| T009 | PUT | `/warehouse/material-batches/{id}/iqc` | IQC 确认 |
