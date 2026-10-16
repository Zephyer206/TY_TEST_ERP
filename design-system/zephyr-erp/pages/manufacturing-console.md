# Page Override: Manufacturing Control Console

> **PAGE ARCHETYPE:** Control Console (operations monitoring, hierarchical data, exception handling)
> **OVERRIDES:** This file overrides `../MASTER.md` for manufacturing control views

---

**Generated:** 2026-08-07
**Density:** 10/10 (Maximum density for multi-level operations monitoring)
**Motion:** 3/10 (Purposeful - status transitions and alert entry)

---

## Color Overrides

| Role | Hex | CSS Variable | Override Reason |
|------|-----|--------------|-----------------|
| Primary | `#1E40AF` | `--color-primary` | Keep MASTER - operational blue |
| Accent/CTA | `#D97706` | `--color-accent` | Keep MASTER - attention amber |
| Status Success | `#059669` | `--color-status-success` | Production on-track green |
| Status Warning | `#D97706` | `--color-status-warning` | Quality alert amber |
| Status Error | `#DC2626` | `--color-status-error` | Exception red |
| Status Info | `#0284C7` | `--color-status-info` | Pending cyan |
| Status Neutral | `#64748B` | `--color-status-neutral` | Not started slate |
| Background Dark | `#F1F5F9` | `--color-background-dark` | Console panel dividers |

**Palette:** Operational blue + semantic status spectrum — optimized for rapid status scanning

---

## Spacing Overrides (Control Console Density)

| Token | Value | Usage | Override |
|-------|-------|-------|----------|
| `--space-xs` | `2px` | Status badge gaps | ✓ Keep |
| `--space-sm` | `4px` | Control button padding | ✓ Keep |
| `--space-md` | `8px` | Panel padding, hierarchy indent | ✓ Keep |
| `--space-lg` | `12px` | Section dividers | ✓ Keep |
| `--space-xl` | `16px` | Control bar padding | ✓ Keep |
| `--space-2xl` | `20px` | Console panel gaps | ✓ Reduced from 24px |
| `--hierarchy-indent` | `20px` | Nested row indentation | ✓ New token |

---

## Typography Overrides

- **Panel Headers:** Fira Sans 600, 15px, uppercase, letter-spacing 0.8px
- **Status Labels:** Fira Sans 500, 12px, uppercase, letter-spacing 0.5px
- **Data Values:** Fira Code 400, 14px (plan IDs, quantities, dates)
- **Hierarchical Labels:** Fira Sans 400, 14px with indent-based hierarchy
- **Exception Messages:** Fira Sans 500, 13px, bold for critical errors
- **Line Height:** 1.3 (very tight for dense console layout)

---

## Manufacturing Status Semantics

### Status Hierarchy

```css
/* Status badge base */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

/* Status variants */
.status-success {
  background: #D1FAE5;
  color: #065F46;
  border-left: 3px solid #059669;
}

.status-warning {
  background: #FEF3C7;
  color: #92400E;
  border-left: 3px solid #D97706;
}

.status-error {
  background: #FEE2E2;
  color: #991B1B;
  border-left: 3px solid #DC2626;
}

.status-info {
  background: #E0F2FE;
  color: #075985;
  border-left: 3px solid #0284C7;
}

.status-neutral {
  background: #F1F5F9;
  color: #475569;
  border-left: 3px solid #64748B;
}
```

### Status Mapping (Business Logic)

| Manufacturing State | CSS Class | Label | Icon |
|---------------------|-----------|-------|------|
| Not Started | `status-neutral` | NOT STARTED | circle-outline |
| In Progress | `status-info` | IN PROGRESS | clock-rotating |
| On Hold | `status-warning` | ON HOLD | pause-circle |
| Quality Issue | `status-warning` | QUALITY ALERT | triangle-exclamation |
| Completed | `status-success` | COMPLETED | circle-check |
| Failed / Rejected | `status-error` | EXCEPTION | circle-xmark |
| Data Quality Issue | `status-error` | DATA ERROR | database-exclamation |

---

## Component Specs: Control Console Pattern

### Console Layout (Three-Column Grid)

```css
.console-layout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  grid-template-rows: 64px 1fr;
  gap: 0;
  height: 100vh;
  background: var(--color-background);
}

.console-header {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  background: var(--color-primary);
  color: var(--color-on-primary);
  border-bottom: 2px solid var(--color-border);
  z-index: 100;
}

.console-sidebar {
  grid-row: 2;
  background: var(--color-background-dark);
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  padding: 12px;
}

.console-main {
  grid-row: 2;
  overflow-y: auto;
  padding: 16px;
}

.console-inspector {
  grid-row: 2;
  background: var(--color-background-dark);
  border-left: 1px solid var(--color-border);
  overflow-y: auto;
  padding: 16px;
}
```

### Hierarchical Data Table

```css
.hierarchy-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 14px;
}

.hierarchy-table thead th {
  position: sticky;
  top: 0;
  background: var(--color-muted);
  border-bottom: 2px solid var(--color-border);
  padding: 8px 12px;
  text-align: left;
  font-weight: 500;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  z-index: 10;
}

.hierarchy-table tbody tr {
  border-bottom: 1px solid var(--color-border);
  transition: background-color 150ms ease;
  cursor: pointer;
}

.hierarchy-table tbody tr:hover {
  background: var(--color-muted);
}

.hierarchy-table tbody tr.expanded {
  background: #F1F5F9;
  font-weight: 500;
}

.hierarchy-table tbody tr.has-error {
  background: #FEE2E2;
  border-left: 4px solid var(--color-status-error);
}

.hierarchy-table tbody tr.has-warning {
  background: #FEF3C7;
  border-left: 4px solid var(--color-status-warning);
}

.hierarchy-table tbody td {
  padding: 6px 12px;
  vertical-align: middle;
}

/* Hierarchy indentation */
.hierarchy-table .level-0 .hierarchy-label { padding-left: 8px; }
.hierarchy-table .level-1 .hierarchy-label { padding-left: 28px; }
.hierarchy-table .level-2 .hierarchy-label { padding-left: 48px; }
.hierarchy-table .level-3 .hierarchy-label { padding-left: 68px; }

/* Expand/collapse indicator */
.hierarchy-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-right: 6px;
  cursor: pointer;
  transition: transform 150ms ease;
}

.hierarchy-toggle.expanded {
  transform: rotate(90deg);
}
```

### Control Bar (Actions + Filters)

```css
.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  gap: 12px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  z-index: 50;
}

.control-bar-section {
  display: flex;
  gap: 8px;
  align-items: center;
}

.control-bar-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-foreground);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.control-bar-input {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 160px;
}

.control-bar-button {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
  white-space: nowrap;
}

.control-bar-button:hover {
  background: var(--color-muted);
  border-color: var(--color-primary);
}

.control-bar-button.primary {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

.control-bar-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

### Exception Panel (Inspector View)

```css
.exception-panel {
  background: white;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
}

.exception-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.exception-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.exception-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.exception-body {
  font-size: 13px;
  line-height: 1.4;
  color: var(--color-foreground);
}

.exception-meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  font-size: 12px;
  color: #64748B;
}

.exception-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.exception-action-btn {
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: white;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
}

.exception-action-btn:hover {
  background: var(--color-muted);
}
```

### Data Quality Indicator

```css
.data-quality-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.data-quality-badge.complete {
  background: #D1FAE5;
  color: #065F46;
}

.data-quality-badge.incomplete {
  background: #FEF3C7;
  color: #92400E;
}

.data-quality-badge.invalid {
  background: #FEE2E2;
  color: #991B1B;
}

/* Data quality tooltip (show on hover) */
.data-quality-tooltip {
  position: absolute;
  background: #1E293B;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
  max-width: 280px;
  box-shadow: var(--shadow-lg);
  z-index: 1000;
  pointer-events: none;
}
```

### Production Metrics Dashboard

```css
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background: white;
  border-radius: 8px;
  padding: 12px;
  box-shadow: var(--shadow-sm);
  border-left: 4px solid var(--color-primary);
}

.metric-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.metric-value {
  font-family: 'Fira Code', monospace;
  font-size: 24px;
  font-weight: 600;
  color: var(--color-foreground);
  line-height: 1;
}

.metric-trend {
  font-size: 12px;
  color: #64748B;
  margin-top: 4px;
}

.metric-trend.positive {
  color: var(--color-status-success);
}

.metric-trend.negative {
  color: var(--color-status-error);
}
```

---

## Motion: Purposeful State Transitions

- **Status change:** `200ms ease` with subtle scale pulse (1.0 → 1.05 → 1.0)
- **Row expand/collapse:** `250ms ease` height animation + rotate icon
- **Alert entry:** `300ms ease` slide-in from right (inspector panel)
- **Control bar actions:** `150ms ease` button hover/press
- **Hierarchy toggle:** `150ms ease` rotation + children fade-in
- **Loading states:** Skeleton pulse (1s interval) with subtle opacity shift

**Rationale:** Motion conveys state changes and system response, crucial for operations monitoring. Avoid decorative animation.

```js
// Status change pulse (GSAP)
gsap.timeline()
  .to(statusBadge, { scale: 1.05, duration: 0.1, ease: 'power1.out' })
  .to(statusBadge, { scale: 1.0, duration: 0.1, ease: 'power1.in' });

// Row expand (GSAP)
gsap.to(childRows, {
  height: 'auto',
  opacity: 1,
  duration: 0.25,
  ease: 'power2.out',
  stagger: 0.03
});

// Alert entry (GSAP)
gsap.from(alertPanel, {
  x: 50,
  opacity: 0,
  duration: 0.3,
  ease: 'power2.out'
});
```

---

## Business Display Rules (Manufacturing Console)

### Production Plan Hierarchy

```
Level 0: Production Plan (plan_id, date_range, status)
  Level 1: Tooling Work Package (TWP) (tooling_id, customer, status)
    Level 2: Part Orders (part_number, quantity, status)
      Level 3: Manufacturing Operations (operation_type, status, quality_data)
```

### Data Quality Rules

1. **Missing Critical Fields**
   - Show `data-quality-badge.invalid` when required fields are null
   - Inspector panel lists missing fields with corrective action buttons

2. **Inconsistent References**
   - Highlight rows with `has-warning` when foreign key references are ambiguous
   - Example: TWP references multiple shared mold sources

3. **Excel Import Conflicts**
   - Show `data-quality-badge.incomplete` when Excel original differs from normalized value
   - Allow drill-down to see original vs. normalized comparison

4. **Validation Failures**
   - Show `has-error` styling for business rule violations
   - Example: cavity count mismatch between part and tooling

### Exception Handling Workflow

1. **Exception Detection**
   - System auto-detects data quality issues, status anomalies, validation failures
   - Display exception count badge in control bar
   - Sort exceptions by severity (error > warning > info)

2. **Exception Review**
   - Click row with `has-error` → inspector panel shows exception details
   - Exception panel displays: type, affected entity, root cause, suggested fix

3. **Exception Resolution**
   - Action buttons: "Correct Data", "Override Rule", "Mark Reviewed", "Escalate"
   - Resolution triggers status update and audit log entry

### Column Visibility (Console Context)

**Always Visible:**
- Hierarchy label (plan → TWP → part → operation)
- Status badge
- Critical identifiers (plan_id, part_number, tooling_id)
- Data quality indicator
- Exception count (if > 0)

**Contextual (Show on Demand):**
- Timestamps (created_at, updated_at)
- User assignments (assigned_to, reviewed_by)
- Audit fields (Excel original, import source)
- Detailed metrics (cycle time, yield, defect rate)

---

## Element Plus Customization (Console)

```css
/* Override Element Plus for control console density */
.console-main .el-table {
  --el-table-row-height: 38px;
  --el-table-header-height: 42px;
  font-size: 14px;
}

.console-main .el-table__header th {
  background: var(--color-muted) !important;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.console-main .el-table__body tr.has-error {
  background: #FEE2E2 !important;
  border-left: 4px solid var(--color-status-error);
}

.console-main .el-table__body tr.has-warning {
  background: #FEF3C7 !important;
  border-left: 4px solid var(--color-status-warning);
}

/* Compact tree table expansion */
.console-main .el-table__expand-icon {
  width: 16px;
  height: 16px;
  font-size: 12px;
}

.console-main .el-table__expanded-cell {
  padding: 8px 12px;
  background: var(--color-background-dark);
}

/* Inline status select */
.console-main .el-select {
  width: 140px;
}

.console-main .el-select .el-input__inner {
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  padding: 4px 8px;
}

/* Inspector panel form controls */
.console-inspector .el-form-item {
  margin-bottom: 12px;
}

.console-inspector .el-form-item__label {
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.console-inspector .el-input__inner,
.console-inspector .el-textarea__inner {
  font-size: 13px;
}
```

---

## Accessibility

- **Keyboard Navigation:**
  - Tab: Move between control bar controls, hierarchy toggle buttons, action buttons
  - Arrow keys: Navigate hierarchy (Up/Down = rows, Right = expand, Left = collapse)
  - Enter: Activate selected row or button
  - Space: Toggle row selection or checkbox
  - Escape: Close inspector panel or cancel action

- **Screen Reader:**
  - Console regions: aria-label for sidebar, main, inspector
  - Hierarchy: aria-level, aria-expanded, aria-owns for tree structure
  - Status badges: aria-label with full status text (not just color)
  - Exception count: aria-live="polite" region for new exceptions
  - Control bar: aria-controls linking filters to table

- **Focus Management:**
  - Visible focus ring (3px solid var(--color-ring))
  - Focus trap in modal exception resolution dialogs
  - Restore focus to trigger element after dialog close

- **ARIA Roles:**
  - Hierarchy table: role="treegrid"
  - Status badges: role="status"
  - Exception panel: role="complementary" with aria-label
  - Control bar: role="toolbar"

---

## Responsive Behavior

| Breakpoint | Behavior |
|------------|----------|
| < 768px | Single-column stack: hide sidebar, main full-width, inspector becomes bottom sheet modal |
| 768-1024px | Two-column: collapse sidebar to icons-only, main + inspector side-by-side |
| 1024-1440px | Three-column standard layout, narrow inspector (240px) |
| > 1440px | Three-column expanded layout, full inspector (320px) |

**Mobile Strategy (< 768px):**
- Control bar becomes vertical stack with collapsible filter section
- Hierarchy table shows only 3 columns: label, status, actions (horizontal scroll for others)
- Inspector triggered by row tap → slides up as bottom sheet (80% viewport height)
- Exception count badge in floating action button (bottom-right)

**Tablet Strategy (768-1024px):**
- Sidebar collapses to 64px icon bar (expand on hover)
- Main area uses 60% width, inspector 40%
- Hierarchy shows 6-8 columns
- Control bar wraps to 2 rows if needed

---

## Anti-Patterns for Control Consoles

- ❌ Auto-refresh without user control (use manual refresh button or pause/play toggle)
- ❌ Modal dialogs for exception review (use inspector panel for context preservation)
- ❌ Decorative animations that delay status updates
- ❌ Hiding critical exceptions below the fold (sticky exception summary bar)
- ❌ Client-side polling every <5s (use WebSocket for real-time updates)
- ❌ Mixing hierarchy levels in flat table (maintain strict parent-child structure)
- ❌ Cryptic status codes (use human-readable labels with icon + color)
- ❌ Requiring clicks to reveal error messages (show inline or in persistent inspector)
- ❌ Single-level undo (maintain operation history for multi-step rollback)
- ❌ Infinite scroll in console views (use paginated or virtualized lists for performance)

---

## Performance Optimization

### Virtualization

- Use virtual scrolling for hierarchies > 100 rows (El-Table's `height` prop + virtual-scroll)
- Lazy-load child rows on expand (not all at initial render)
- Debounce filter inputs (300ms) to avoid excessive re-renders

### Real-Time Updates

- WebSocket connection for status changes (not HTTP polling)
- Optimistic UI updates (show change immediately, rollback on error)
- Batch status updates (max 1 update per second per visible row)

### Memory Management

- Unload collapsed child rows from DOM (keep in state only)
- Limit inspector panel history to 20 recent items
- Clear exception cache after resolution (keep audit log server-side)

---

## Integration Notes

- **Backend API Requirements:**
  - GET `/api/production-plans` (hierarchical tree structure)
  - PATCH `/api/production-plans/{id}/status` (status updates)
  - GET `/api/exceptions` (active data quality issues)
  - POST `/api/exceptions/{id}/resolve` (exception resolution workflow)
  - WebSocket `/ws/manufacturing-status` (real-time status push)

- **State Management:**
  - Pinia store for console state (hierarchy expansion, filters, selections)
  - Separate store for exception queue (FIFO with priority sorting)
  - LocalStorage for user preferences (column visibility, sidebar collapse state)

- **Audit Trail:**
  - Log all status changes with user + timestamp
  - Track exception resolution actions
  - Record data correction history (Excel original → normalized → manual override)
