# Page Override: Part Detail

> **PAGE ARCHETYPE:** Dossier-first (comprehensive record view, tabbed sections, inline editing)
> **OVERRIDES:** This file overrides `../MASTER.md` for part detail/dossier views

---

**Generated:** 2026-08-07
**Density:** 9/10 (Dense but with strategic breathing room for complex forms)
**Motion:** 2/10 (Subtle tab transitions, field validation feedback)

---

## Color Overrides

| Role | Hex | CSS Variable | Override Reason |
|------|-----|--------------|-----------------|
| Primary | `#0D9488` | `--color-primary` | Teal for edit-mode indicators |
| Secondary | `#2DD4BF` | `--color-secondary` | Light teal for active tab |
| Accent/CTA | `#D97706` | `--color-accent` | Amber for save/submit actions |
| Muted | `#E8F1F4` | `--color-muted` | Cool gray for read-only fields |

**Palette:** Teal edit indicators + amber submit — optimized for edit-heavy workflows

---

## Spacing Overrides

| Token | Value | Usage | Override |
|-------|-------|-------|----------|
| `--space-md` | `8px` | Field vertical gaps | ✓ Keep |
| `--space-lg` | `12px` | Form group padding | ✓ Keep |
| `--space-xl` | `20px` | Tab content padding | ✓ Increased from 16px |
| `--space-2xl` | `28px` | Section dividers | ✓ Increased from 24px |
| `--space-3xl` | `40px` | Header padding | ✓ Increased from 32px |

---

## Layout: Dossier Structure

The detail view is an archive-style workbench, not a modal stack:

```text
| Chapter navigation | Business record and relation tables | Source evidence + change history |
| 220px               | minmax(520px, 1fr)                  | 300px                            |
```

On desktop, keep the chapter list visible while the center record scrolls. The right evidence rail is read-only and shows import source, row reference, and change history. On narrower screens, stack these regions in that order and keep the chapter list as a compact sticky tab bar.

```css
.part-dossier {
  display: grid;
  grid-template-columns: 220px minmax(520px, 1fr) 300px;
  min-height: 0;
}

.part-dossier__chapters,
.part-dossier__evidence {
  position: sticky;
  top: 0;
  align-self: start;
  max-height: calc(100vh - 120px);
  overflow: auto;
}

@media (max-width: 1023px) {
  .part-dossier { grid-template-columns: 1fr; }
  .part-dossier__chapters,
  .part-dossier__evidence { position: static; max-height: none; }
}
```

```
┌─────────────────────────────────────────────────────────┐
│ Header (Part Number, Status, Quick Actions)            │
├─────────────────────────────────────────────────────────┤
│ Tab Bar: [基本信息] [工艺] [模具] [历史] [文档]          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tab Content Area (2-3 column responsive grid)         │
│                                                         │
│  [ Field Groups with Edit Indicators ]                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Footer: Modified timestamp, Save/Cancel buttons        │
└─────────────────────────────────────────────────────────┘
```

---

## Component Specs: Dossier Pattern

### Header

```css
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: var(--color-background);
  border-bottom: 2px solid var(--color-border);
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title h1 {
  font-family: 'Fira Code', monospace;
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  background: var(--color-muted);
  color: var(--color-foreground);
}

.quick-actions {
  display: flex;
  gap: 8px;
}
```

### Tab Navigation

```css
.detail-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background);
  padding: 0 24px;
  gap: 2px;
}

.detail-tab {
  padding: 12px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-foreground);
  border-bottom: 3px solid transparent;
  transition: all 200ms ease;
  position: relative;
  top: 1px;
}

.detail-tab:hover {
  background: var(--color-muted);
}

.detail-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: white;
}

/* Edit mode indicator on tab */
.detail-tab.has-changes::after {
  content: '●';
  color: var(--color-accent);
  margin-left: 6px;
  font-size: 10px;
}
```

### Form Grid (Responsive)

```css
.detail-content {
  padding: 24px;
  background: white;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px 24px;
}

/* Denser grid for simple fields */
.form-grid.dense {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px;
}

/* Full-width fields */
.form-field.full-width {
  grid-column: 1 / -1;
}
```

### Form Fields (Read/Edit States)

```css
.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-field label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-foreground);
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Required indicator */
.form-field label.required::after {
  content: '*';
  color: var(--color-destructive);
}

/* Read-only state */
.form-field .read-only {
  padding: 8px 12px;
  background: var(--color-muted);
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 14px;
  color: var(--color-foreground);
  min-height: 38px;
  display: flex;
  align-items: center;
}

/* Editable state */
.form-field input,
.form-field select,
.form-field textarea {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  transition: all 200ms ease;
  background: white;
}

.form-field input:focus,
.form-field select:focus,
.form-field textarea:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
}

/* Modified indicator */
.form-field.modified label::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
  margin-right: 4px;
}

/* Validation error */
.form-field.error input,
.form-field.error select,
.form-field.error textarea {
  border-color: var(--color-destructive);
}

.form-field .error-message {
  font-size: 12px;
  color: var(--color-destructive);
  margin-top: 2px;
}
```

### Field Groups (Collapsible Sections)

```css
.field-group {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 20px;
}

.field-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-muted);
  border-radius: 8px 8px 0 0;
  cursor: pointer;
  user-select: none;
}

.field-group-header h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.field-group-body {
  padding: 16px;
  background: white;
}

.field-group.collapsed .field-group-body {
  display: none;
}
```

### Excel Original Values (Conditional Display)

```css
/* Only shown when value differs from imported Excel */
.excel-diff-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
  padding: 2px 8px;
  background: #FEF3C7;
  border: 1px solid #F59E0B;
  border-radius: 4px;
  font-size: 12px;
  color: #92400E;
  cursor: help;
}

.excel-diff-indicator:hover .excel-original-tooltip {
  display: block;
}

.excel-original-tooltip {
  display: none;
  position: absolute;
  background: #1F2937;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 100;
  margin-top: 4px;
}
```

---

## Motion: Subtle Edit Feedback

- **Tab switch:** `250ms ease` horizontal slide (CSS `translate`)
- **Field focus:** `200ms ease` border color + box-shadow
- **Save button:** `200ms ease` background + slight lift on hover
- **Validation error:** `300ms ease` shake animation (translate -4px → +4px → 0)
- **Section collapse:** `200ms ease` height transition

**No animation:**
- Read-only to edit mode toggle (instant)
- Field value updates (instant)
- Modified indicator appearance (instant)

---

## Business Display Rules (ERP-Specific)

### Editing Concentration

**Rule:** All edits happen in detail views, never in list views.

- List views: read-only, double-click to edit
- Detail views: edit mode toggled per field group or entire form
- Inline table editors: only for child entities (e.g., tooling work parts within a part)

### ID Visibility

**Never show autogenerated IDs:**
- Part ID → Show `part_number` instead
- Material ID → Show `material_grade` instead
- Tooling ID → Show `tooling_code` instead

**Only show IDs in:**
- Debug mode (admin users)
- Relation selectors (hidden in dropdown value, shown in option text)

### Customer Alias Display

**Rule:** Suppress irrelevant aliases

```
If current context is "Customer A part detail":
  - Show Customer A's part number prominently
  - Show other customers' aliases in "其他客户件号" section
  - Omit Customer A from "other" section (redundant)
```

### Excel Import Tracking

**Three-state display:**

1. **No Excel source:** Normal field display, no indicator
2. **Excel matches current:** No indicator (user accepted import)
3. **User modified after import:** Show amber diff indicator with original value in tooltip

```html
<div class="form-field">
  <label>产品名称</label>
  <div class="read-only">
    Bearing Housing
    <span class="excel-diff-indicator" title="Excel原值: Bearing Hsng">
      ⚠ 已修改
    </span>
  </div>
</div>
```

---

## Element Plus Customization

```css
/* Form components */
.el-form-item {
  margin-bottom: 16px; /* Reduced from default 22px */
}

.el-form-item__label {
  font-size: 13px;
  font-weight: 500;
  padding-bottom: 4px;
}

.el-input__inner,
.el-select .el-input__inner,
.el-textarea__inner {
  font-size: 14px;
  padding: 8px 12px;
  border-radius: 6px;
}

/* Tabs */
.el-tabs__header {
  margin: 0;
  border-bottom: 1px solid var(--color-border);
}

.el-tabs__item {
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 500;
  height: auto;
}

.el-tabs__item.is-active {
  color: var(--color-primary);
}

.el-tabs__active-bar {
  background-color: var(--color-primary);
  height: 3px;
}

/* Description list (read-only data pairs) */
.el-descriptions__label {
  font-weight: 500;
  color: var(--color-foreground);
  background: var(--color-muted);
}

.el-descriptions__content {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
}
```

---

## Tab Organization Strategy

**Primary Tabs (for Part detail):**

1. **基本信息** — Part number, name, category, dimensions, material
2. **工艺** — Process routes, operation sequences, standard times
3. **模具** — Shared molds, tooling work parts, cavity configurations
4. **客户** — Customer aliases, specifications, pricing
5. **历史** — Modification log, Excel import history, audit trail
6. **文档** — Attachments, drawings, technical documents

**Tab loading strategy:**
- First tab: Load immediately
- Other tabs: Lazy load on first click
- Unsaved changes: Warn before tab switch

---

## Accessibility

- **Keyboard Navigation:**
  - Tab: Move between fields
  - Shift+Tab: Move backward
  - Arrow keys: Navigate tabs
  - Enter: Activate focused button
  - Escape: Cancel inline edit / close dialog

- **Form Validation:**
  - Required fields: `aria-required="true"`
  - Error fields: `aria-invalid="true"` + `aria-describedby` linking to error message
  - Success: `aria-live="polite"` announcement on save

- **Read-only Mode:**
  - Fields: `aria-readonly="true"` or disabled state
  - Visual distinction: muted background + no cursor-pointer

---

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| < 768px | Single column, stacked fields, horizontal tab scroll |
| 768-1024px | 2-column grid for simple fields, full-width for complex |
| 1024-1440px | 2-3 column grid, sidebar for metadata |
| > 1440px | 3-column grid, persistent sidebar, more horizontal space |

---

## Anti-Patterns for Detail Views

- ❌ Auto-save without user control (use explicit Save button)
- ❌ Modal dialogs for related entity creation (use inline forms or drawer)
- ❌ Breadcrumb navigation that resets unsaved changes
- ❌ Refreshing data while user is editing
- ❌ Long forms without section grouping
- ❌ Validation errors only shown on submit (validate on blur)
