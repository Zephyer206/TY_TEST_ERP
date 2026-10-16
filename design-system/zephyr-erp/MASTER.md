# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Zephyr ERP
**Generated:** 2026-08-07 14:42:41
**Category:** Manufacturing ERP Workbench
**Design Dials:** Variance 3/10 (Centered / Minimal) | Motion 2/10 (Subtle) | Density 10/10 (Dense / Dashboard)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#176B5A` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#60717A` | `--color-secondary` |
| Accent/CTA | `#D97706` | `--color-accent` |
| Background | `#F6F7F8` | `--color-background` |
| Foreground | `#1F2933` | `--color-foreground` |
| Muted | `#EEF1F2` | `--color-muted` |
| Border | `#D9DEE1` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| Ring | `#176B5A` | `--color-ring` |

**Color Notes:** Neutral work surfaces with restrained teal identity and semantic green, amber, and red status colors.

### Typography

- **Heading Font:** Fira Code
- **Body Font:** Fira Sans
- **Mood:** dashboard, data, analytics, code, technical, precise
- **Google Fonts:** [Fira Code + Fira Sans](https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

*Density: 10/10 — Dense / Dashboard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `2px` / `0.125rem` | Tight gaps |
| `--space-sm` | `4px` / `0.25rem` | Icon gaps, inline spacing |
| `--space-md` | `8px` / `0.5rem` | Standard padding |
| `--space-lg` | `12px` / `0.75rem` | Section padding |
| `--space-xl` | `16px` / `1rem` | Large gaps |
| `--space-2xl` | `24px` / `1.5rem` | Section margins |
| `--space-3xl` | `32px` / `2rem` | Major page section spacing |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 8px 20px rgba(15,23,42,0.12)` | Drawers and focused overlays |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #D97706;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #1E40AF;
  border: 2px solid #1E40AF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F8FAFC;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 16px;
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #1E40AF;
  outline: none;
  box-shadow: 0 0 0 3px #1E40AF20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 6px;
  padding: 24px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Restrained Industrial Workbench

**Keywords:** Odoo-inspired, dense data, neutral surfaces, clear hierarchy, operational clarity

**Best For:** Manufacturing operations, parts catalogs, quality control, production planning

**Key Effects:** 1px dividers, restrained shadows for overlays, 150-200ms feedback, and no hero-scale typography or decorative gradients in business views.

### Layout Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `4px` | Inputs and compact controls |
| `--radius-md` | `6px` | Data panels and dialogs |
| `--control-height` | `32px` | Dense desktop controls |
| `--row-height` | `36px` | Dense data tables |
| `--content-max` | `1600px` | Wide workbench content |
| `--sidebar-width` | `232px` | Desktop navigation shell |

Breakpoints: `768px` (tablet), `1024px` (desktop), `1440px` (wide). At tablet widths, filters collapse into a drawer and detail evidence moves below business fields; do not create page-level horizontal scroll.

### Page Archetypes

- **List-first:** search, filters, batch actions, dense table, stable pagination; rows open details.
- **Dossier-first:** left chapter navigation, central business fields, right source and change evidence; edit mode is entered explicitly in the detail view.
- **Manufacturing control console:** production plan queue, data-quality queue, exception panel, and status summaries; prioritize scanability over decoration.

### Navigation Boundary

The primary navigation has exactly four domains: 产品, 工艺与生产, 库存, 客户与报价. Settings is a bottom utility entry. Do not restore the former fragmented sidebar or add unrelated top-level entries.

### ERP Display Rules

- Never expose autogenerated part, material, or relation IDs in user-facing views.
- Suppress customer aliases outside the customer relationship context.
- Keep edits in detail views; list rows are for search, selection, and navigation.
- Show an Excel original value only when it differs from the current user-maintained value; otherwise render one value.
- Preserve incomplete T/W/P values and mark them for review; never infer missing data.

---

## Motion

**Scroll Reveal** (Subtle) — Trigger: scroll (viewport enter) | Duration: 300-400ms | Easing: `power1.out`

```js
gsap.from(el, { opacity: 0, y: 12, duration: 0.35, ease: 'power1.out', scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none reverse' } });
```

**Framework notes:** Requires the ScrollTrigger plugin registered once via gsap.registerPlugin(ScrollTrigger)

- ✅ Keep the y offset small (8-16px) so it reads as a fade, not a slide
- ❌ Don't reveal below-the-fold content needed for SEO/crawlers as invisible-by-default without a no-JS fallback
- ⚡ toggleActions 'play none none reverse' avoids re-triggering on every scroll direction change

---

### Workbench Motion Override

Use only short state feedback for row selection, filter application, save progress, drawer open/close, and alert arrival. Keep transitions within 150-200ms, preserve spatial continuity, and provide an equivalent no-motion state under `prefers-reduced-motion: reduce`. Do not use scroll-triggered reveals or animation to communicate data that must be immediately scannable.

## Anti-Patterns (Do NOT Use)

- ❌ Ornate design
- ❌ No filtering

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y
- ❌ **Marketing composition** — No hero blocks, oversized display type, decorative gradients, or card-within-card layouts in business views
- ❌ **One-note palette** — Use neutral surfaces with semantic status colors only for business meaning

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
