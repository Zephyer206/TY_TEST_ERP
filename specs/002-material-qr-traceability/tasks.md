# Tasks: Material QR Traceability System

**Feature**: 002-material-qr-traceability
**Input**: `spec.md` (P1/P2 用户故事), `checklists/requirements.md`
**Prerequisites**: `specs/001-erp-system-architecture/` (核心模型已实现)

---

## 关键设计决策

### 原料批次：单表自引用方案

所有原料批次（母卷 + 子卷）均存储在 `material_batches` 表，通过 `parent_batch_id` 自引用形成树状关系。

**原因**：子卷扫码时需同时展示母卷 + 同胞子卷，单表 `parent_batch_id` 自引用使追溯查询（正向/反向/横向）全部在一张表内完成，无需跨表 JOIN。

**示例数据**：

| id | batch_no | qr_code | parent_batch_id | 说明 |
|----|----------|---------|----------------|------|
| 1 | MAT-20260613-001 | MAT:1:20260613 | NULL | 母卷 |
| 2 | MAT-20260613-002 | MAT:2:20260613 | 1 | 子卷A |
| 3 | MAT-20260613-003 | MAT:3:20260613 | 1 | 子卷B |

**溯源规则**：

- 扫码子卷 → 展示：子卷台账 + 母卷台账 + 同胞子卷列表
- 扫码母卷（状态 PARTIAL）→ 展示：母卷台账 + 所有子卷列表
- 每个 qr_code 全局唯一，不可复用

---

## Phase 1: Setup (Shared Infrastructure)

| Task | Description |
|------|-------------|
| [x] T001 | 创建 `alembic/versions/qr002_material_traceability.py` 迁移：material_batches.qr_code 唯一非空、material_batch_children.child_qr_code、新增 qr_scan_logs 表、batch_transactions.operator_id、parent_batch_id 索引 |
| [x] T002 [P] | 修复 `src/api/qr.py` 中字段名错误：Machine.machine_name → machine_no；Machine.status → state；Part.part_number → part_no；Part.internal_name → part_name；Tooling.tooling_name → name；Tooling.status → state |
| [x] T003 [P] | 修复 `src/api/qr.py` 第 22 行：`from app.services import qr_service` → `from src.services import qr_service`；同步修复 `src/api/warehouse.py` 的导入 |

---

## Phase 2: Foundational (Blocking Prerequisites)

### 2.1 QRScanLog 模型

| Task | Description |
|------|-------------|
| [x] T004 | 在 `src/models/warehouse.py` 新增 `ScanType` 枚举（MAT/MCN/PFC/PRT）和 `ScanOperation` 枚举（query/split/consume/report/inbound）。新增 `QRScanLog` 模型，字段：id, scan_type, entity_id, entity_no, operator_id, operation, notes, scanned_at |
| [x] T005 | 在 `src/schemas/warehouse.py` 新增 QRScanLogCreate、QRScanLogResponse、MaterialBatchScanResponse、MaterialBatchChildScanResponse Schema |

### 2.2 QR 扫码日志 API

| Task | Description |
|------|-------------|
| [x] T006 | 在 `src/api/warehouse.py` 新增 POST `/warehouse/scans`：记录扫码日志 |
| [x] T007 | 在 `src/api/warehouse.py` 新增 GET `/warehouse/scans/{entity_type}/{entity_id}`：查询某实体的扫码历史 |

---

## Phase 3: US1 — 原料进厂赋码 + US2 — 大卷分条衍生（MVP）

> MVP = US1 + US2，端到端跑通：原料入库赋码 → 分条子卷独立赋码 → 扫码查询完整追溯链。

### 3.1 QR 内容生成（US1/US2 共用）

| Task | Description |
|------|-------------|
| [x] T008 | 在 `src/services/qr_service.py` 新增 `generate_material_batch_qr(batch_id)`：生成 `MAT:{batch_id}:{YYYYMMDD}` |
| [x] T009 | 在 `src/services/qr_service.py` 新增 `generate_material_batch_qr_base64(batch_id)`：生成 base64 图片供打印 |

### 3.2 原料登记入库时自动赋码（US1）

| Task | Description |
|------|-------------|
| [x] T010 | 修改 `src/services/material_batch_service.py` 的 `create_material_batch()`：flush 后生成 qr_code 并持久化 |
| [x] T011 | 确认 `POST /warehouse/material-batches` 已集成自动赋码（由 T010 覆盖） |

### 3.3 扫码查询原料台账（US1）

| Task | Description |
|------|-------------|
| [x] T012 | 在 `src/api/warehouse.py` 新增 GET `/warehouse/material-batches/scan/{batch_id}`：扫码台账，记录日志，返回 qr_image_base64 |

### 3.4 查询原料流转记录（US1）

| Task | Description |
|------|-------------|
| [x] T013 | `GET /warehouse/material-batches/{batch_id}/trace` 已有（原有实现） |

### 3.5 大卷分条生成子卷（US2）

| Task | Description |
|------|-------------|
| [x] T014 | 重写 `split_batch()`：从创建 MaterialBatchChild 改为创建独立 MaterialBatch（单表自引用），每个子卷独立 qr_code；记录分条事务 + 各子卷入库事务 |
| [x] T015 | 修改 `POST /warehouse/material-batches/{batch_id}/split` 响应类型为 `MaterialBatchScanResponse[]`，返回各子卷 qr_code + qr_image_base64 |

### 3.6 扫码查询子卷 + 横向追溯（US2）

| Task | Description |
|------|-------------|
| [x] T016 | 在 `src/api/warehouse.py` 新增 GET `/warehouse/material-batches/scan/child/{child_id}`：返回子卷台账 + 母卷完整信息 + 同胞子卷列表（横向追溯） |
| [x] T017 | 在 `src/api/warehouse.py` 新增 GET `/warehouse/material-batches/{batch_id}/children`：返回母卷下所有子卷列表 |

---

## Phase 4: US3 — 机台设备二维码（非 MVP）

| Task | Description |
|------|-------------|
| [x] T018 | 在 `src/services/machine_service.py` 新增 `generate_machine_qr(machine_id)` |
| [x] T019 | 在 `src/api/machines.py` 新增 POST `/machines/{machine_id}/generate-qr` |
| [x] T020 | 在 `src/api/machines.py` 新增 GET `/machines/scan/{machine_id}` |

---

## Phase 5: US4 — 产品工艺流转单生成与赋码（非 MVP）

| Task | Description |
|------|-------------|
| [x] T021 | 在 `src/services/qr_service.py` 新增 `generate_process_flow_qr(card_id)` |
| [x] T022 | 在 `src/services/session_service.py` 修改 `close_session()` 自动生成 ProcessFlowCard + qr_code |
| [x] T023 | 在 `src/api/production.py` 新增 GET `/production/process-flow-cards/scan/{card_id}` |
| [x] T024 | 在 `src/api/production.py` 新增 GET `/production/process-flow-cards/{card_id}/reverse-trace` |

---

## Phase 6: US5 — 全检入库扫码确认（非 MVP）

| Task | Description |
|------|-------------|
| [x] T025 | 在 `src/api/production.py` 新增 PUT `/production/process-flow-cards/{card_id}/inbound` |

---

## Phase 7: Edge Cases

| Task | Description |
|------|-------------|
| [x] T026 | 在 `src/api/warehouse.py` 新增 POST `/warehouse/material-batches/{batch_id}/reprint-qr` |
| [x] T027 | 在 `src/api/production.py` 新增 POST `/production/process-flow-cards/{card_id}/reprint-qr` |
| [x] T028 | 在 `src/api/qr.py` 新增 GET `/qr/lookup?manual=true&type=MAT&code=xxx` |

---

## Phase 8: Integration & Polish

| Task | Description |
|------|-------------|
| [x] T029 | 在 `specs/002-material-qr-traceability/` 新增 `quickstart.md`：提供 US1+US2 场景的 curl 验证命令 |
| [x] T030 | 运行 quickstart.md 验证场景，确保端到端可工作 |

---

## 任务依赖图

```
T001(迁移) → T002(T003并行)
                      ↓
T004(QRScanLog模型) → T005(Schema) → T006(T007扫码日志API)
                                              ↓
T008~T009(QR生成函数) → T010(T011)
                                      ↓
T012(US1-扫码台账) ← T010
T013(US1-流转记录已有)
                                      ↓
T014(单表分条) ← T008~T009
T015(分条API改响应)
                                      ↓
T016(US2-子卷扫码+横向追溯)
T017(US2-母卷查子卷列表)
                                      ↓
T018~T020(US3-机台二维码)
                                      ↓
T021~T024(US4-流转单)
                                      ↓
T025(US5-入库确认)
                                      ↓
T026~T028(边界情况)
                                      ↓
T029~T030(验证)
```

## 任务统计

| 类别 | 数量 | 已完成 |
|------|------|--------|
| Setup | 3 | 3 |
| Foundational | 4 | 4 |
| US1+US2（原料+分条） | 10 | 10 |
| US3 机台二维码 | 3 | 3 |
| US4 工艺流转单 | 4 | 4 |
| US5 全检入库 | 1 | 1 |
| Edge Cases | 3 | 3 |
| Integration | 2 | 2 |
| **总计** | **30** | **30** |

## MVP 范围（首批交付）

**MVP = US1（原料进厂赋码）+ US2（大卷分条衍生），共 18 个任务：**

- T001, T002, T003（Setup）
- T004, T005, T006, T007（Foundational）
- T008, T009, T010, T011（QR 生成 + 入库赋码）
- T012, T013（扫码查询台账 + 流转记录）
- T014, T015, T016, T017（分条 + 子卷横向追溯）
- T029（quickstart.md）
- T030 ✅（psql 端到端验证通过：US1 入库赋码 + US2 分条子卷 + 扫码日志，2026-06-13）

**MVP 验收场景（按 spec.md SC-001 ~ SC-003）：**

1. 原料到厂 → 登记入库 → 二维码 5 分钟内可打印
2. 扫码原料二维码 → 展示完整台账（含 qr_image_base64）
3. 大卷分条 → 子卷二维码 2 分钟内可打印（每个独立 QR）
4. 扫码子卷 → 展示母卷 + 同胞子卷，溯源链完整
