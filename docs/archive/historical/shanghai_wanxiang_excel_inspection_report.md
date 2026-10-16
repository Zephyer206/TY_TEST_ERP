# Excel Workbook Inspection Report: 上海万向.xlsx

**Date**: 2026-07-18  
**Purpose**: Read-only inspection for future Zephyr ERP page redesign and import strategy  
**File**: `C:\Users\WIT_User\Documents\xwechat_files\uhaohan_2ed1\msg\file\2026-07\上海万向.xlsx`

---

## Executive Summary

This Excel workbook contains a **price quotation system** with 3 sheets, 14 embedded product images, and complex formulas for cost calculation. The workbook structure indicates it's a customer-specific quote document for "上海万向" (Shanghai Wanxiang) with pricing data from 2025 year-end.

---

## Workbook Metadata

- **Total files in archive**: 36
- **Worksheets**: 3 active sheets (4 XML files, 1 empty)
- **Sheet names**:
  1. **Sheet3** (ID: 3, rId: rId1) - *appears unused or hidden*
  2. **Sheet1** (ID: 1, rId: rId2) - **Main quote sheet with images and calculations**
  3. **报价2025年底** (ID: 5, rId: rId3) - **Reference data: Quote 2025 Year-End**
- **Embedded media**: 15 files (14 images: 7 PNG, 7 JPEG + 1 directory entry)
- **Shared strings**: 101 unique text entries
- **Active sheet**: Sheet3

---

## Sheet 1: Main Quote Sheet (sheet1.xml)

### Dimensions & Structure
- **Range**: A1:W27 (23 columns × 27 rows)
- **Merged cells**: 133 ranges (heavy use of vertical merging)
- **Images**: 14 product images referenced via `DISPIMG()` formulas in column B

### Header Row (Row 1) - 23 Columns

Due to encoding issues in the terminal output, the exact Chinese headers are partially corrupted. Based on patterns observed:

| Column | Likely Header | Type |
|--------|---------------|------|
| A | 原图零件编号 (Original Part Number) | ID |
| B | (Image) | Image |
| C | 原图零件描述1 (Part Description 1) | Text |
| D | 模具类型 (Mold Type) | Text |
| E | 材料 (Material) | Text |
| F | 材料规格 (Material Spec: T×W×H) | Formula input |
| G | 备注 (Notes) | Text |
| H | 毛坯(g) (Blank weight) | Calculated |
| I | 产品单重(g) (Product unit weight) | Input |
| J | 材料价格 (Material price) | Calculated |
| K | 材料价格 (Material price alt) | Calculated |
| L | 材料成本 (Material cost) | Calculated |
| M | 回收 (Recovery) | Calculated |
| N | 涂油 (Oil coating) | Input/Calculated |
| O | 表面处理 (Surface treatment) | Sum formula |
| P | 成本 (Cost) | Total calculated |
| Q | 2025单价 (2025 Unit Price) | XLOOKUP from Sheet3 |
| R | 2025数量 (2025 Quantity) | XLOOKUP from Sheet3 |
| S | 报价金额 (Quote Amount) | Calculated (Q×R) |
| T | 2025第一次发货 (1st delivery) | Manual input |
| U | 2025第二次发货 (2nd delivery) | Manual input |
| V | 2025第三次发货 (3rd delivery) | Manual input |
| W | 2025第四次发货 (4th delivery) | Manual input |

### Merged Cell Patterns

**Critical Finding**: Rows are merged in pairs (e.g., B5:B6, B7:B8) across columns B through P. This indicates:
- **Each logical product spans 2 Excel rows**
- Primary data in odd rows (5, 7, 9, 11...)
- Secondary/paired part numbers in even rows (6, 8, 10, 12...)
- Merged cells share values: material specs, weights, costs

**Merged column pattern** (11 merges each in columns B, E, F, H, I, J, K, L, M, N, O, P):
- Rows 5:6, 7:8, 9:10, 11:12, 13:14, 15:16, 17:18, 19:20, 21:22, 23:24, 25:26

### Image References (Column B)

14 images referenced via Excel's `_xlfn.DISPIMG()` formula:
- Format: `=_xlfn.DISPIMG("ID_<GUID>", 1)`
- Example IDs:
  - `ID_E09F77B3F4254CDCB9896C7D8D072434` (Part 60004065)
  - `ID_62E1A6FD4D8F4784BD5687ABB792043B` (Part 60000485)
  - `ID_40444DEFAA31449298A6AF8D1D6D6EF0` (Part 60004195)

**Image storage**: 14 physical files in `xl/media/` (image1.png through image14.jpeg, mixed PNG/JPEG formats)

**Critical Risk**: DISPIMG image IDs are **internal Excel GUIDs** with no direct file path mapping accessible via XML. The relationship between GUID and actual image file (image1.png, image2.png...) requires Excel's internal image cache or COM automation to resolve.

### Data Rows (Rows 2-27)

**Sample Part Entry (Rows 2-3)**:

Row 2 (Primary):
- A2: `60004065` (Part number)
- B2: `DISPIMG formula` (Image)
- C2: Part description (friction plate)
- D2: Mold type (progressive die)
- E2: `SUS301-CSP 3/4H (JIS G4305)` (Material)
- F2: `0.4*77*77` (Material spec: thickness×width×height mm)
- H2: **Formula**: Calculate blank weight from F2 dimensions × density 7.93 g/cm³
- I2: `8` (Product unit weight, grams)
- J2-P2: **Cost calculation formulas** (material price, recovery, coating, total cost)
- Q2-R2: **XLOOKUP formulas** referencing `报价2025年底!A:A` to fetch price and quantity
- S2: **Formula**: Total quote amount (Q2 × R2)
- T2-W2: Delivery schedule (`/` indicates no delivery)

Row 3 (Secondary entry for different part):
- A3: `60000485` (Different part number)
- Same formula pattern, **but uses H3 hardcoded value** `23.054096` instead of formula

**Pattern observations**:
- Rows with merged cells (5-6, 7-8...) represent **paired parts** sharing physical characteristics
- Even rows (6, 8, 10...) contain only: part number (A), XLOOKUP formulas (Q, R), calculated quote (S), delivery schedule (T-W)
- Material cost formulas reference:
  - `20/1000` (material price factor)
  - `7/1000` (scrap/recovery rate)
  - `15/1000` (recovery value multiplier)

### Formula Dependencies

Sheet1 formulas **heavily depend on Sheet3** (`报价2025年底`):
```excel
Q2: =_xlfn.XLOOKUP(A2, 报价2025年底!A:A, 报价2025年底!C:C)  // Lookup unit price
R2: =_xlfn.XLOOKUP(A2, 报价2025年底!A:A, 报价2025年底!B:B, 0)  // Lookup quantity
S2: =Q2*R2  // Calculate total quote amount
```

**Error handling**: Some XLOOKUP formulas return `#N/A` (e.g., rows 9-10 for parts 60008581/60008582), indicating missing data in the reference sheet.

---

## Sheet 2: Part-Customer Mapping (sheet2.xml)

### Dimensions
- **Range**: A1:D26 (4 columns × 26 rows)
- **No merged cells**
- **Simple lookup table structure**

### Headers (Row 1)
| Column | Header | Content Type |
|--------|--------|--------------|
| A | 零件编号 (Part Number) | Internal part ID |
| B | 零件名称 (Part Name) | Part category |
| C | 客户件号 (Customer Part Number) | Customer's reference number |
| D | 单价（包含税） (Unit Price incl. Tax) | Price per unit |

### Data Sample (Rows 2-15)
```
60004065 | 离合片 | 11Q00140 | 0.8565
60000485 | 离合片 | 11Q00142 | 1.0922
60004309 | 离合片 | 11Q00138 | 0.5006
60004310 | 离合片 | 11Q00120 | 0.5006
60004195 | 离合片-摩擦片 | 11Q00139 | 0.9676
60006825 | 离合片 | 11Q00119 | 0.5805
60006826 | 离合片 | 11Q00137 | 0.5805
...
```

**Purpose**: Maps internal part numbers (60xxxxxx) to customer-specific part numbers (11Q00xxx) with unit pricing.

**Critical for import**: This establishes the **Part ↔ Customer ↔ Price** relationship. Customer part numbers must NOT be written back to internal part master data.

---

## Sheet 3: Reference Pricing Data (sheet3.xml - "报价2025年底")

### Dimensions
- **Range**: A1:D27 (4 columns × 27 rows)
- **No merged cells**
- **Pure data table (no formulas)**

### Headers (Row 1)
| Column | Header | Content Type |
|--------|--------|--------------|
| A | 零件号 (Part Number) | Internal part ID |
| B | 数量:数值型 (Quantity: Numeric) | Order quantity |
| C | 价格 (Price) | Unit price |
| D | 报价金额 (Quote Amount) | Total amount (B × C) |

### Data Sample (Rows 2-15)
```
60000485 | 126000  | 1.0376 | 130737.6
60004195 | 42000   | 0.9192 | 38606.4
60004309 | 4500    | 0.4806 | 2162.7
60004310 | 4500    | 0.4806 | 2162.7
60006825 | 743200  | 0.5457 | 405564.24
60006826 | 742740  | 0.5457 | 405313.218
60009467 | 660436  | 0.5548 | 366409.8928
60009468 | 639789  | 0.5548 | 354954.9372
...
```

**Purpose**: Historical pricing reference for 2025 year-end quotes. Sheet1 uses XLOOKUP to pull prices and quantities from this sheet.

**Data quality**: Complete data for most parts, but missing entries for parts 60008581/60008582 (causing #N/A errors in Sheet1).

---

## Data Relationships & Import Strategy

### Identified Entity Relationships

```
[Part] ←──────────────────────┐
   ↓                           │
   │ (internal part_id)        │ (XLOOKUP)
   ↓                           │
[Sheet2: Part-Customer Map]    │
   ↓                           │
   │ (customer_part_number)    │
   ↓                           │
[Customer] ←───────────────────┤
                                │
[Sheet3: 2025 Pricing] ─────────┘
   ↓ (price, quantity)
   │
[Sheet1: Quote Calculation]
   ↓ (with images, formulas)
   │
[Quote Line Items]
```

### Critical Ambiguities Requiring User Confirmation

#### 1. **Paired Part Rows (Merged Cells)**
- **Issue**: Rows 5-6, 7-8, etc. are merged across columns B-P
- **Observation**: 
  - Row 5: Part 60004309 with full specs
  - Row 6: Part 60004310 with only part number + pricing, shares specs from row 5
- **Question**: Are these:
  - **Option A**: Variant parts (e.g., left/right, different customer items) sharing same material/process?
  - **Option B**: Multiple customer part numbers for the same internal part?
  - **Option C**: Paired parts sold together as a set?
- **Import impact**: Determines whether to create separate part records or use part variants/bundles

#### 2. **Image-to-Part Mapping**
- **Issue**: DISPIMG formulas use internal GUIDs, not sequential file names
- **Observation**: 14 images exist as image1.png through image14.jpeg
- **Risk**: No reliable way to map `ID_E09F77B3F4254CDCB9896C7D8D072434` → `image1.png` without Excel COM automation
- **Question**: 
  - Should images be imported **by ordinal position** (row 2 → image1, row 3 → image2)?
  - Should images be **manually matched** post-import?
  - Should images be **re-embedded** via user selection?
- **Import impact**: May require manual image association step in UI

#### 3. **Customer Identification**
- **Issue**: No explicit customer name/ID in structured data
- **Observation**: Filename is "上海万向.xlsx" (Shanghai Wanxiang)
- **Question**: 
  - Is "上海万向" the customer name to import?
  - Should customer be looked up by name or customer part numbers (11Q00xxx)?
  - Is customer pre-existing in Zephyr ERP?
- **Import impact**: Customer entity must exist before importing part-customer mappings

#### 4. **Sheet2 vs Sheet3 Pricing Conflict**
- **Issue**: Two different prices for same parts:
  - Sheet2: `60004065 → 0.8565` (unit price incl. tax)
  - Sheet3: Part 60004065 not in Sheet3, but Sheet1 uses Sheet3 XLOOKUP
- **Question**: 
  - Which price is authoritative?
  - Is Sheet2 "base price" and Sheet3 "quote-specific price"?
  - Should import prefer Sheet3 (customer-specific quote) over Sheet2 (general pricing)?
- **Import impact**: Determines which price to store in ERP `CustomerPartPrice` table

#### 5. **Material Specification Parsing**
- **Issue**: Column F contains formulas as text: `0.4*77*77` (thickness × width × height)
- **Observation**: Some formulas in column H parse this string to calculate weight
- **Question**: 
  - Should `T*W*H` be parsed and stored in separate fields?
  - Should it remain as a single text field in part specs?
  - How to handle inconsistent formats (some with `/2` division)?
- **Import impact**: Affects part specification data model

#### 6. **Quote Line Items vs Part Master**
- **Issue**: Sheet1 contains calculated costs and delivery schedules
- **Question**: 
  - Should this be imported as a **Quote** entity with line items?
  - Or should only **Part master data** be imported (from Sheet2/3)?
  - Should delivery schedules (columns T-W) be imported as separate delivery records?
- **Import impact**: Determines which ERP tables to populate (parts vs quotes vs deliveries)

---

## Proposed Import Strategy (Evidence-Based)

### Phase 1: Reference Data Import (No Ambiguity)
**Source**: Sheet 3 ("报价2025年底")  
**Target**: Temporary staging table or direct import to `Quote` / `QuoteLineItem`

1. Import as historical quote reference:
   - Part number (A) → link to existing `Part.part_number`
   - Quantity (B) → `quantity`
   - Unit price (C) → `unit_price`
   - Total amount (D) → `total_amount` (validate B × C = D)

2. **Validation**:
   - Check all part numbers exist in Zephyr `Part` table
   - Flag missing parts (60008581, 60008582, etc.) for creation

### Phase 2: Customer-Part Mapping (Requires Customer Confirmation)
**Source**: Sheet 2  
**Target**: `CustomerPartPrice` or `CustomerPart` junction table

**Pre-requisite**: Confirm customer entity
- Lookup/create customer: "上海万向" (Shanghai Wanxiang)

1. Import mappings:
   - Internal part (A) → `Part.part_number`
   - Customer part number (C) → `CustomerPart.customer_part_number`
   - Unit price (D) → `CustomerPartPrice.unit_price`

2. **Validation**:
   - Never write customer part numbers (11Q00xxx) to `Part.part_number`
   - Preserve Excel as source of truth: store original row/sheet reference

### Phase 3: Part Master Enhancement (Requires Merge Strategy Confirmation)
**Source**: Sheet 1 rows 2-27  
**Target**: `Part` table fields (material, weight, dimensions)

1. For each **non-merged row** (primary parts):
   - Part number (A)
   - Description (C) → `Part.name_chinese` or `description`
   - Mold type (D) → `Part.mold_type_id` (lookup mold type)
   - Material (E) → `Part.material_id` (lookup material)
   - Material spec (F) → `Part.material_specification` (text field)
   - Product weight (I) → `Part.unit_weight`
   - Notes (G) → `Part.notes`

2. For **merged rows** (paired parts):
   - **Decision needed**: Create separate part with reference to primary part?
   - **Option**: Store as `Part.variant_of_part_id` → parent part

### Phase 4: Image Handling (Manual Association Required)
**Source**: 14 files in `xl/media/`, DISPIMG formulas in Sheet1 column B  
**Target**: `Part.image_url` or separate `PartImage` table

**Recommended approach** (safest):
1. Extract all 14 images from Excel archive → temp directory
2. Create UI page showing:
   - Part number (A)
   - Description (C)
   - Image preview thumbnails (all 14 images)
   - Manual selection dropdown
3. User clicks to associate correct image with each part
4. Upload selected images to Zephyr storage
5. Update `Part.image_url` after confirmation

**Alternative** (risky): Import by ordinal position (row order), require manual correction if wrong

### Phase 5: Quote Entity Creation (Optional)
**Source**: Sheet 1 complete data  
**Target**: `Quote` + `QuoteLineItem` tables

If user wants to preserve this as a formal quote:
1. Create `Quote` record:
   - Customer: "上海万向"
   - Quote date: derived from "2025年底" (2025 year-end)
   - Status: historical/reference
2. Create `QuoteLineItem` for each part:
   - Part number (A)
   - Quantity (R) from XLOOKUP
   - Unit price (Q) from XLOOKUP
   - Total amount (S)
   - Delivery schedule (T, U, V, W) → separate delivery records?

---

## Import UI Decisions Requiring User Confirmation

### 1. Import Scope Selection
- [ ] Import only Part master data (Sheet2 + Sheet1 specs)
- [ ] Import Part-Customer mappings (Sheet2)
- [ ] Import pricing reference (Sheet3)
- [ ] Import as complete Quote with line items
- [ ] Import delivery schedules

### 2. Merged Row Handling
- [ ] **Option A**: Treat paired parts as variants (store `variant_of_part_id`)
- [ ] **Option B**: Import only primary rows, skip merged secondary rows
- [ ] **Option C**: Create separate part records, copy shared specs from primary

### 3. Customer Identification
- [ ] Customer name: `上海万向` (from filename)
- [ ] Auto-create customer if not exists
- [ ] User selects existing customer from dropdown

### 4. Pricing Authority
- [ ] Prefer Sheet3 prices (quote-specific)
- [ ] Prefer Sheet2 prices (base pricing)
- [ ] Import both: Sheet2 as base, Sheet3 as quote override

### 5. Image Import Strategy
- [ ] **Manual association UI** (recommended): Show thumbnails, user clicks to match
- [ ] **Ordinal import** (risky): Row 2→image1, Row 3→image2, etc.
- [ ] **Skip images**: Import data only, images added later

### 6. Material Spec Parsing
- [ ] Parse `T*W*H` into separate fields (`thickness`, `width`, `height`)
- [ ] Store as single text field (`material_specification`)

### 7. Formula Preservation
- [ ] Store calculated values only (H, J-P columns)
- [ ] Store formula logic in metadata for audit trail
- [ ] Ignore formulas, import result values

### 8. Error Handling
- [ ] Flag missing parts (60008581, 60008582) for manual creation
- [ ] Skip rows with #N/A errors
- [ ] Create placeholder parts with "needs review" flag

---

## Technical Import Constraints

### Preserve Excel as Source of Truth
- **Never invent relationships**: Only import explicitly stated mappings
- **Store Excel metadata**: 
  - Original filename: `上海万向.xlsx`
  - Sheet name: `Sheet1`, `Sheet2`, `报价2025年底`
  - Row number: for audit trail
  - Last modified date: from Excel file metadata

### Data Validation Rules
1. **Part numbers must exist** before creating customer mappings
2. **Customer must exist** before creating part-customer relationships
3. **Material/mold types** must be looked up from existing Zephyr reference tables
4. **Never write customer part numbers to Part.part_number**
5. **Validate formula results**: If Sheet1 column S = Q × R, verify calculation

### Import Atomicity
- Use database transactions: rollback on any validation error
- Log all import decisions for audit trail
- Create `ImportLog` record with:
  - Source file name
  - Import date
  - User who imported
  - Row-level mapping (Excel row → ERP record ID)

---

## Recommended Import UI Flow

```
1. [File Upload] 
   User uploads 上海万向.xlsx
   ↓
2. [Sheet Preview]
   Show all 3 sheets with row counts
   User selects sheets to import
   ↓
3. [Customer Confirmation]
   "Detected customer: 上海万向"
   [Select existing] or [Create new customer]
   ↓
4. [Data Preview & Validation]
   Show first 5 rows from each sheet
   Highlight validation errors (missing parts, #N/A)
   User confirms or fixes errors
   ↓
5. [Merge Strategy Selection]
   Show merged row pairs (5-6, 7-8...)
   User picks: Variants / Skip secondary / Separate parts
   ↓
6. [Image Association]
   For each part with DISPIMG formula:
   - Show part number + description
   - Show 14 image thumbnails
   - User clicks correct image
   - Or user selects "Skip" to add image later
   ↓
7. [Pricing Source Selection]
   "Found prices in Sheet2 and Sheet3, which to use?"
   [Sheet2 base price] [Sheet3 quote price] [Both]
   ↓
8. [Import Execution]
   Show progress bar:
   - Creating/updating parts... (X/27)
   - Creating customer mappings... (Y/25)
   - Uploading images... (Z/14)
   ↓
9. [Import Summary]
   ✓ Created: 15 parts
   ✓ Updated: 12 parts
   ✓ Customer mappings: 25
   ✓ Images uploaded: 14
   ⚠ Warnings: 2 parts missing in Sheet3
   [View Import Log] [Download Error Report]
```

---

## Risk Assessment

### High Risk (Requires User Decision)
1. **Image GUID mapping**: No programmatic way to map DISPIMG IDs to files
2. **Merged row semantics**: Unclear if variants, bundles, or duplicates
3. **Customer identification**: Filename-based, not in structured data

### Medium Risk (Can Be Validated)
4. **Pricing conflicts**: Two sheets with different prices
5. **Missing parts**: Parts in Sheet1/2 not in Sheet3 (causes #N/A)
6. **Formula dependencies**: XLOOKUP assumes specific sheet structure

### Low Risk (Automatable)
7. **Material spec parsing**: Consistent format `T*W*H`
8. **Part number format**: All 8-digit `60xxxxxx` format
9. **Customer part numbers**: All `11Q00xxx` format

---

## Next Steps

1. **User provides clarification** on 8 confirmation points above
2. **Design import UI mockup** based on confirmed strategy
3. **Create staging tables** for temporary import data
4. **Implement validation rules** before writing to production tables
5. **Build image association UI** for manual matching
6. **Test import with this file** as pilot before generalizing

---

## Files Generated (For Reference)
- `inspect_excel.py` - Initial workbook structure inspection
- `analyze_excel_detailed.py` - Deep data analysis with formulas
- This report: `shanghai_wanxiang_excel_inspection_report.md`

**Note**: Temporary Python scripts can be deleted after import strategy is finalized.
