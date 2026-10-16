# Zephyr ERP Design System

> **Purpose:** Persistent design system for Zephyr ERP UI refactor
> **Framework:** Vue 3 + Element Plus
> **Philosophy:** Restrained, high-density manufacturing workbench inspired by Odoo

---

**Generated:** 2026-08-07  
**Version:** 1.0.0  
**Status:** Stage 1 Complete — Ready for implementation

---

## Overview

This design system provides comprehensive guidance for the Zephyr ERP frontend refactor. It defines semantic tokens, component specifications, page archetypes, navigation structure, and business display rules specific to manufacturing ERP workflows.

### Design Principles

1. **High Density** — Maximum information per screen (dense spacing, compact components)
2. **Minimal Motion** — Subtle transitions only; no decorative animation
3. **Restrained Palette** — Blue operational tones + amber accents
4. **Odoo-Inspired IA** — Four primary domains, minimal depth, predictable structure
5. **Edit-Heavy Workflows** — All edits in detail views, never in list views
6. **Data Transparency** — No internal IDs visible, Excel diffs shown conditionally

---

## File Structure

```
design-system/zephyr-erp/
├── MASTER.md              # Global design tokens and defaults
├── README.md              # This file
├── NAVIGATION.md          # Navigation structure and routing
├── ELEMENT-PLUS.md        # Element Plus customization guide
├── RESPONSIVE.md          # Responsive behavior and breakpoints
├── ACCESSIBILITY.md       # WCAG 2.1 AA compliance guidelines
└── pages/
    ├── parts-list.md              # List-first archetype
    ├── part-detail.md             # Dossier-first archetype
    └── manufacturing-console.md   # Control console archetype
```

---

## Usage

### Master + Override Pattern

**When building a page:**

1. **Always read `MASTER.md` first** — Global tokens, colors, typography, spacing
2. **Check for page-specific override** — If `pages/{page-name}.md` exists, its rules override Master
3. **Apply overrides selectively** — Only override what's explicitly documented; inherit everything else

**Example: Building the parts list view**

```typescript
// 1. Read MASTER.md for global tokens
const globalColors = { primary: '#1E40AF', accent: '#D97706', ... }
const globalSpacing = { xs: '2px', sm: '4px', md: '8px', ... }

// 2. Read pages/parts-list.md for overrides
const listOverrides = { 
  primary: '#334155',  // Override: Industrial slate
  accent: '#059669',   // Override: Stock green
  // spacing inherits from MASTER (no override)
}

// 3. Merge: Override wins
const effectiveTokens = { ...globalColors, ...listOverrides }
```

---

## Core Design Tokens

### Color Palette (MASTER.md)

| Role | Hex | CSS Variable | Usage |
|------|-----|--------------|-------|
| Primary | `#1E40AF` | `--color-primary` | Operational blue (headers, active states) |
| Accent | `#D97706` | `--color-accent` | Amber (CTA buttons, attention) |
| Success | `#059669` | `--color-success` | Green (completed status) |
| Warning | `#F59E0B` | `--color-warning` | Amber (quality alerts) |
| Destructive | `#DC2626` | `--color-destructive` | Red (errors, delete actions) |
| Background | `#F8FAFC` | `--color-background` | Page background |
| Foreground | `#1E3A8A` | `--color-foreground` | Primary text |

### Typography

- **Heading Font:** Fira Code (monospace for technical precision)
- **Body Font:** Fira Sans (clean sans-serif for readability)
- **Base Size:** 14px (dense dashboard sizing)
- **Line Height:** 1.5 (1.3-1.4 for console views)

### Spacing Scale (Density: 10/10)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `2px` | Tight gaps, row dividers |
| `--space-sm` | `4px` | Icon gaps, cell padding |
| `--space-md` | `8px` | Standard padding |
| `--space-lg` | `12px` | Section padding |
| `--space-xl` | `16px` | Large gaps |
| `--space-2xl` | `24px` | Section margins |
| `--space-3xl` | `32px` | Hero padding |

---

## Three Page Archetypes

### 1. List-First (e.g., Parts List)

**Purpose:** Browse, filter, and select from high-volume data

**Characteristics:**
- Dense data table (36px row height)
- Sticky headers
- Inline sorting/filtering
- Batch operations toolbar
- Double-click → detail view

**Override:** `pages/parts-list.md`

**Key Components:**
- `el-table` with custom density
- Toolbar with filters
- Pagination (compact)
- No inline editing

---

### 2. Dossier-First (e.g., Part Detail)

**Purpose:** Comprehensive record view with inline editing

**Characteristics:**
- Tabbed sections (基本信息, 工艺, 模具, 客户, 历史)
- 2-3 column responsive form grid
- Read-only → edit mode toggle
- Modified indicators (amber dots)
- Excel diff tracking

**Override:** `pages/part-detail.md`

**Key Components:**
- `el-tabs` for section organization
- `el-form` with inline validation
- Field groups (collapsible)
- Excel original value tooltips

---

### 3. Control Console (e.g., Manufacturing Console)

**Purpose:** Real-time monitoring, status oversight, exception handling

**Characteristics:**
- Three-column grid (sidebar + main + inspector)
- Hierarchical data tables (expandable rows)
- Status indicators (color + icon + text)
- Real-time updates (10-30 sec intervals)
- Alert panel with severity

**Override:** `pages/manufacturing-console.md`

**Key Components:**
- KPI metric cards
- Production line status grid
- Real-time charts
- Alert queue

---

## Navigation Structure

### Four Primary Domains

```
┌─────────────────────────────────────────────────────┐
│  [产品]  [工艺与生产]  [库存]  [客户与报价]          │
└─────────────────────────────────────────────────────┘
```

1. **产品 (Products)** — Parts, materials, categories
2. **工艺与生产 (Process & Production)** — Console, routes, molds, tooling
3. **库存 (Inventory)** — Stock levels, inbound, outbound
4. **客户与报价 (Customers & Quotations)** — Customers, pricing, orders

**See:** `NAVIGATION.md` for full structure, routing, and mobile patterns

---

## Business Display Rules

### ID Visibility

**Never show autogenerated internal IDs in UI:**
- ❌ `part.id`, `material.id`, `tooling_work_part.id`
- ✓ `part_number`, `material_grade`, `customer_part_number`

### Customer Alias Display

**Suppress redundant aliases:**
- If viewing "Customer A" parts, omit Customer A from customer alias list
- Show other customers' aliases in "其他客户件号" section

### Excel Import Tracking

**Three states:**
1. **No Excel source** — Normal display
2. **User accepted import** — No indicator
3. **User modified after import** — Amber diff indicator with original value in tooltip

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

### Modulus vs. Cavity

**Terminology clarity:**
- **模数** — Shared mold module count (mold-level attribute)
- **穴数** — Part-specific cavity count (tooling_work_part attribute)
- Never use generic "Cavities" label without context

---

## Element Plus Integration

### Global Theme Configuration

**Install and configure:**

```bash
npm install element-plus
```

**main.ts:**
```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/element-variables.css'  // Custom tokens

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')
```

**See:** `ELEMENT-PLUS.md` for complete customization guide

### Key Customizations

- Table row height: `36px` (reduced from default `48px`)
- Form item margin: `16px` (reduced from `22px`)
- Button primary color: `#D97706` (amber accent)
- Input focus shadow: Primary with 10% opacity

---

## Responsive Strategy

### Breakpoints

| Device | Width | Layout |
|--------|-------|--------|
| Desktop (primary) | ≥ 1200px | Multi-column, all panels visible |
| Tablet landscape | 992-1199px | 2-column, collapsible panels |
| Tablet portrait | 768-991px | Single column, drawer overlays |
| Mobile (emergency) | < 768px | Card lists, bottom tab nav |

**Primary target:** 1440px+ desktop workstations  
**Mobile:** Emergency access only (simplified views)

**See:** `RESPONSIVE.md` for breakpoint implementation

---

## Accessibility

### WCAG 2.1 Level AA Compliance

**Key requirements:**
- ✓ Contrast ratio 4.5:1 minimum for text
- ✓ Keyboard navigation for all interactive elements
- ✓ Visible focus indicators
- ✓ Screen reader support with ARIA labels
- ✓ Form labels always visible (no placeholder-only)
- ✓ Motion respects `prefers-reduced-motion`

**See:** `ACCESSIBILITY.md` for complete guidelines

---

## Implementation Checklist

**Before starting development:**
- [ ] Read `MASTER.md` in full
- [ ] Identify page archetype (list-first / dossier-first / console)
- [ ] Read corresponding page override (if exists)
- [ ] Review `NAVIGATION.md` for routing structure
- [ ] Check `ELEMENT-PLUS.md` for component customization

**During development:**
- [ ] Use CSS variables from MASTER.md
- [ ] Apply page-specific overrides where documented
- [ ] Follow business display rules (no internal IDs, Excel diffs)
- [ ] Test keyboard navigation
- [ ] Verify color contrast
- [ ] Test at 1440px, 1024px, 768px breakpoints

**Before code review:**
- [ ] Run accessibility audit (axe DevTools or Lighthouse)
- [ ] Verify responsive behavior
- [ ] Check focus states are visible
- [ ] Confirm motion respects reduced-motion preference
- [ ] Validate against page archetype specifications

---

## FAQ

### Q: Can I change the primary color?

**A:** Only with user approval. The blue operational palette was chosen specifically for manufacturing context. If changing, update `MASTER.md` first, then regenerate page overrides.

### Q: Which archetype for my new page?

**A:** 
- High-volume data browsing → **List-first** (parts list, order list)
- Comprehensive record editing → **Dossier-first** (part detail, customer detail)
- Real-time monitoring → **Control console** (production lines, equipment status)

### Q: Should I create a new page override?

**A:** Only if the page needs different colors, spacing, or motion from MASTER.md. Most pages can use MASTER.md directly. Overrides are for archetypes with fundamentally different density/motion needs.

### Q: Can I use Tailwind CSS classes?

**A:** No. This project uses Element Plus + custom CSS variables. Introducing Tailwind would create conflicting spacing/color systems. Use utility classes defined in `ELEMENT-PLUS.md` instead.

### Q: How do I handle dark mode?

**A:** Dark mode is optional (not required for Phase 1). If implementing, follow the dark mode section in `ELEMENT-PLUS.md`. Primary use case: night-shift manufacturing console operators.

### Q: What about mobile-first?

**A:** This is a **desktop-first** ERP system. Manufacturing workstations are the primary target. Mobile is emergency access only with simplified views. Responsive strategy is in `RESPONSIVE.md`.

---

## Design Decisions Log

### Density: 10/10 (Maximum)

**Rationale:** Manufacturing users scan hundreds of parts/orders per session. Dense spacing (8px standard, 2-4px tight) maximizes information per screen without scrolling.

**Trade-off:** Less breathing room, but acceptable for expert users in focused workflows.

---

### Motion: 2/10 (Minimal)

**Rationale:** Animation distracts from data absorption in high-volume scanning tasks. Only use motion for user-initiated actions (hover, click, validation).

**Trade-off:** Less "polished" feel, but better task efficiency.

---

### Four-Domain Navigation (vs. sidebar)

**Rationale:** Odoo-style top navigation scales better, avoids sidebar collapse/expand state management, and provides more horizontal space for data tables.

**Trade-off:** Limited to ~6 top-level domains (cognitive load), but Zephyr only needs 4.

---

### Edit in Detail Views Only

**Rationale:** Inline table editing causes state synchronization issues, validation confusion, and accidental edits. Concentrating edits in detail views provides clear edit context.

**Trade-off:** Extra click to edit, but clearer editing affordance and undo behavior.

---

### Excel Diff Tracking

**Rationale:** Many parts/materials imported from Excel. Users need visibility when imported values differ from current database state (manual corrections after import).

**Trade-off:** Extra UI indicator, but critical for data integrity auditing.

---

## Migration Path

**Stage 1 (Complete):** Design system created  
**Stage 2:** Implement global tokens (CSS variables)  
**Stage 3:** Build navigation shell  
**Stage 4:** Refactor parts list (list-first archetype)  
**Stage 5:** Refactor part detail (dossier-first archetype)  
**Stage 6:** Build manufacturing console (control console archetype)  
**Stage 7:** Migrate remaining pages using established archetypes

---

## Support

**Design system questions:** Refer to this README first, then specific doc files  
**Implementation blockers:** Check FAQ above  
**Accessibility questions:** See `ACCESSIBILITY.md` and test with axe DevTools  
**Responsive issues:** See `RESPONSIVE.md` breakpoint guidance

---

## Version History

**1.0.0 (2026-08-07)** — Initial design system creation
- Master tokens defined
- Three page archetypes documented
- Navigation structure finalized
- Element Plus integration guide created
- Responsive strategy defined
- WCAG 2.1 AA accessibility guidelines documented

---

## License & Attribution

**Project:** Zephyr ERP  
**Design System:** Internal use only  
**Typography:** Fira Code & Fira Sans (SIL Open Font License)  
**Icons:** Heroicons or Lucide (MIT License)  
**Framework:** Element Plus (MIT License)
