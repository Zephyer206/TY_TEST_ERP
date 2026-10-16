# Accessibility Guidelines

> **Standard:** WCAG 2.1 Level AA compliance
> **Framework:** Vue 3 + Element Plus with semantic HTML

---

**Generated:** 2026-08-07
**Target Users:** Keyboard operators, screen reader users, manufacturing floor staff

---

## Core Principles

### 1. Perceivable

**Color Contrast:**
- Text on background: minimum 4.5:1 (body text 14px+)
- Large text (18px+ or 14px bold): minimum 3:1
- UI components and graphics: minimum 3:1

**All colors in MASTER.md meet WCAG AA:**
- Primary `#1E40AF` on white: 8.59:1 ✓
- Foreground `#1E3A8A` on white: 10.24:1 ✓
- Accent `#D97706` on white: 4.51:1 ✓
- Destructive `#DC2626` on white: 5.53:1 ✓

**Never rely on color alone:**
```html
<!-- BAD: Color-only status -->
<span class="text-red">Error</span>

<!-- GOOD: Color + icon + text -->
<span class="status-error">
  <el-icon><CircleXmark /></el-icon>
  Error
</span>
```

**Alternative text for images:**
```html
<!-- Icons conveying information -->
<img src="/alert.svg" alt="Warning: Quality issue detected" />

<!-- Decorative images -->
<img src="/pattern.svg" alt="" aria-hidden="true" />
```

---

### 2. Operable

**Keyboard Navigation:**

All interactive elements must be keyboard accessible:

```html
<!-- Native buttons (accessible by default) -->
<button @click="save">Save</button>

<!-- Custom clickable elements need tabindex + role -->
<div 
  role="button" 
  tabindex="0"
  @click="handleClick"
  @keydown.enter="handleClick"
  @keydown.space.prevent="handleClick"
>
  Custom Action
</div>
```

**Focus indicators:**
```css
/* Visible focus state (never remove) */
.el-button:focus-visible,
.el-input:focus-visible,
.custom-control:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* High contrast for critical actions */
.el-button--primary:focus-visible {
  outline-color: var(--color-accent);
  outline-width: 3px;
}
```

**Keyboard shortcuts for ERP workflows:**

| Shortcut | Action | Implementation |
|----------|--------|----------------|
| `/` | Open global search | `@keydown.prevent` on window |
| `Escape` | Close modal/drawer | `@keydown.esc` on overlay |
| `Enter` | Submit form / Open detail | `@keydown.enter` on row |
| `Tab` | Move to next field | Native browser behavior |
| `Shift+Tab` | Move to previous field | Native browser behavior |
| `Arrow keys` | Navigate table rows | Custom `@keydown.arrow` |
| `Space` | Toggle checkbox | Native on `<input type="checkbox">` |

**Skip links:**
```html
<template>
  <div id="app">
    <a href="#main-content" class="skip-link">
      Skip to main content
    </a>
    <nav>...</nav>
    <main id="main-content" tabindex="-1">
      <!-- Page content -->
    </main>
  </div>
</template>

<style>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: 8px 16px;
  text-decoration: none;
  z-index: 1000;
}

.skip-link:focus {
  top: 0;
}
</style>
```

**Focus management in modals:**
```typescript
// When modal opens, trap focus inside
const modalRef = ref<HTMLElement>()

const openModal = () => {
  modalVisible.value = true
  nextTick(() => {
    const firstFocusable = modalRef.value?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    firstFocusable?.focus()
  })
}
```

---

### 3. Understandable

**Form labels (always visible):**
```html
<!-- BAD: Placeholder-only -->
<el-input placeholder="Enter part number" />

<!-- GOOD: Visible label -->
<el-form-item label="Part Number">
  <el-input v-model="partNumber" placeholder="e.g., P-12345" />
</el-form-item>
```

**Required fields:**
```html
<el-form-item 
  label="Part Number" 
  required
  :rules="[{ required: true, message: 'Part number is required' }]"
>
  <el-input v-model="partNumber" />
</el-form-item>
```

**Error messages (inline, near field):**
```html
<el-form-item 
  label="Quantity"
  :error="errors.quantity"
  :validate-status="errors.quantity ? 'error' : ''"
>
  <el-input v-model="quantity" type="number" />
  <span v-if="errors.quantity" class="error-message" role="alert">
    {{ errors.quantity }}
  </span>
</el-form-item>
```

**Clear navigation structure:**
```html
<nav aria-label="Primary navigation">
  <ul>
    <li><a href="/products" aria-current="page">Products</a></li>
    <li><a href="/production">Production</a></li>
    <li><a href="/inventory">Inventory</a></li>
    <li><a href="/customers">Customers</a></li>
  </ul>
</nav>
```

---

### 4. Robust

**Semantic HTML structure:**
```html
<!-- Use correct semantic elements -->
<header>...</header>
<nav>...</nav>
<main>
  <article>
    <h1>Part Detail</h1>
    <section>
      <h2>Specifications</h2>
      ...
    </section>
  </article>
</main>
<footer>...</footer>
```

**ARIA landmarks and roles:**
```html
<div role="search">
  <input type="search" aria-label="Search parts" />
</div>

<table role="grid" aria-label="Parts list">
  <thead>
    <tr>
      <th scope="col">Part Number</th>
      <th scope="col">Name</th>
    </tr>
  </thead>
</table>

<div role="alert" aria-live="assertive">
  Error: Failed to save changes
</div>
```

---

## Component-Specific Accessibility

### Tables (Data Grids)

```html
<el-table 
  :data="parts"
  aria-label="Parts inventory list"
  @row-click="handleRowClick"
>
  <el-table-column 
    prop="partNumber" 
    label="Part Number"
    sortable
  >
    <template #header>
      <span id="part-number-header">Part Number</span>
      <button 
        aria-label="Sort by part number"
        aria-describedby="part-number-header"
      >
        <el-icon><Sort /></el-icon>
      </button>
    </template>
  </el-table-column>
</el-table>
```

**Keyboard navigation in tables:**
```typescript
const handleKeyDown = (event: KeyboardEvent, row: any, index: number) => {
  switch (event.key) {
    case 'Enter':
    case ' ':
      event.preventDefault()
      navigateToDetail(row)
      break
    case 'ArrowDown':
      event.preventDefault()
      focusRow(index + 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      focusRow(index - 1)
      break
  }
}
```

### Tabs (Dossier Navigation)

```html
<el-tabs 
  v-model="activeTab"
  @tab-click="handleTabClick"
>
  <el-tab-pane 
    label="基本信息" 
    name="basic"
    :aria-selected="activeTab === 'basic'"
  >
    <div role="tabpanel" aria-labelledby="tab-basic">
      <!-- Tab content -->
    </div>
  </el-tab-pane>
</el-tabs>
```

### Modals & Dialogs

```html
<el-dialog
  v-model="visible"
  title="Delete Part"
  :aria-labelledby="dialogTitle"
  role="alertdialog"
  aria-modal="true"
>
  <template #header>
    <h2 id="dialogTitle">Delete Part</h2>
  </template>
  
  <p id="dialogDesc">
    Are you sure you want to delete part {{ partNumber }}? This action cannot be undone.
  </p>
  
  <template #footer>
    <el-button @click="visible = false">Cancel</el-button>
    <el-button type="danger" @click="confirmDelete" aria-describedby="dialogDesc">
      Delete
    </el-button>
  </template>
</el-dialog>
```

### Loading States

```html
<!-- Loading indicator with accessible label -->
<el-loading
  v-loading="loading"
  element-loading-text="Loading parts data..."
  element-loading-background="rgba(255, 255, 255, 0.9)"
>
  <div role="status" aria-live="polite">
    <span v-if="loading" class="sr-only">Loading parts data, please wait...</span>
  </div>
</el-loading>
```

### Status Indicators

```html
<!-- Status with semantic meaning -->
<span 
  class="status-badge status-success"
  role="status"
  aria-label="Production status: Completed"
>
  <el-icon><CircleCheck /></el-icon>
  <span>Completed</span>
</span>

<!-- Alert/notification -->
<el-notification
  type="error"
  role="alert"
  aria-live="assertive"
>
  <p>Quality issue detected on Line 3</p>
</el-notification>
```

---

## Screen Reader Support

**Announce dynamic updates:**
```html
<div aria-live="polite" aria-atomic="true" class="sr-only">
  {{ statusMessage }}
</div>
```

**Live region politeness levels:**
- `aria-live="polite"` — Wait for natural pause (status updates, counts)
- `aria-live="assertive"` — Interrupt immediately (errors, critical alerts)
- `aria-live="off"` — Don't announce (default)

**Example: Manufacturing console alerts**
```typescript
const announceAlert = (message: string) => {
  const liveRegion = document.getElementById('console-alerts')
  if (liveRegion) {
    liveRegion.textContent = message
    // Clear after 5 seconds so repeated alerts still announce
    setTimeout(() => {
      liveRegion.textContent = ''
    }, 5000)
  }
}
```

```html
<div 
  id="console-alerts" 
  role="status" 
  aria-live="assertive" 
  aria-atomic="true"
  class="sr-only"
></div>
```

---

## Motion & Animation

**Respect prefers-reduced-motion:**

```css
/* Normal motion */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 300ms ease;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active {
    transition-duration: 0.01ms !important;
  }
  
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Implementation in Vue:**
```typescript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const animationDuration = prefersReducedMotion ? 0 : 300
```

---

## Touch Targets (Mobile/Tablet)

**Minimum size: 44×44px (iOS) / 48×48px (Android)**

```css
/* Ensure touch targets are large enough */
.el-button,
.clickable-icon,
.table-row-action {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Add padding for smaller visual elements */
.small-icon-button {
  width: 24px;
  height: 24px;
  padding: 10px; /* Creates 44×44 touch target */
}
```

---

## Testing Checklist

**Manual testing:**
- [ ] Navigate entire app using keyboard only (no mouse)
- [ ] Test with screen reader (NVDA on Windows, VoiceOver on macOS)
- [ ] Verify focus indicators are visible on all interactive elements
- [ ] Check color contrast with browser DevTools or contrast checker
- [ ] Test forms with validation errors
- [ ] Verify skip links work
- [ ] Test with browser zoom at 200%
- [ ] Enable prefers-reduced-motion and verify animations are minimal

**Automated testing tools:**
- [axe DevTools](https://www.deque.com/axe/devtools/) — Browser extension
- [WAVE](https://wave.webaim.org/) — Web accessibility evaluation tool
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) — Built into Chrome DevTools

**Element Plus a11y support:**
- Element Plus components have built-in ARIA attributes
- Verify they're not being overridden by custom styles
- Test with latest Element Plus version (accessibility improvements ongoing)

---

## Anti-Patterns

- ❌ Removing focus indicators (`outline: none` without replacement)
- ❌ Using `<div>` with `@click` instead of `<button>`
- ❌ Placeholder-only form labels
- ❌ Color as the only indicator of status
- ❌ Auto-playing video/audio without controls
- ❌ Opening modals without focus management
- ❌ Time-based auto-logout without warning
- ❌ Captchas without audio alternative
- ❌ PDF-only documentation (provide HTML version)
- ❌ Icon-only buttons without accessible labels
