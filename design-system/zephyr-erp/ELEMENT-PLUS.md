# Element Plus Customization Guide

> **Framework:** Vue 3 + Element Plus
> **Purpose:** Theme overrides, component customization, ERP-specific patterns

---

**Generated:** 2026-08-07
**Element Plus Version:** 2.x (latest stable)

---

## Global Theme Configuration

### CSS Variables Override

Create `src/styles/element-variables.css`:

```css
:root {
  /* Primary colors from MASTER.md */
  --el-color-primary: #1E40AF;
  --el-color-primary-light-3: #3B82F6;
  --el-color-primary-light-5: #60A5FA;
  --el-color-primary-light-7: #93C5FD;
  --el-color-primary-light-9: #DBEAFE;
  --el-color-primary-dark-2: #1E3A8A;
  
  /* Success (green) */
  --el-color-success: #059669;
  --el-color-success-light-3: #10B981;
  --el-color-success-light-9: #D1FAE5;
  
  /* Warning (amber) */
  --el-color-warning: #D97706;
  --el-color-warning-light-3: #F59E0B;
  --el-color-warning-light-9: #FEF3C7;
  
  /* Danger (red) */
  --el-color-danger: #DC2626;
  --el-color-danger-light-3: #EF4444;
  --el-color-danger-light-9: #FEE2E2;
  
  /* Info (slate) */
  --el-color-info: #334155;
  --el-color-info-light-3: #475569;
  --el-color-info-light-9: #E6E8EA;
  
  /* Backgrounds */
  --el-bg-color: #F8FAFC;
  --el-bg-color-page: #F8FAFC;
  --el-bg-color-overlay: #FFFFFF;
  
  /* Text */
  --el-text-color-primary: #1E3A8A;
  --el-text-color-regular: #334155;
  --el-text-color-secondary: #64748B;
  --el-text-color-placeholder: #94A3B8;
  
  /* Borders */
  --el-border-color: #DBEAFE;
  --el-border-color-light: #E6E8EA;
  --el-border-color-lighter: #F1F5F9;
  --el-border-color-extra-light: #F8FAFC;
  
  /* Typography from MASTER.md */
  --el-font-family: 'Fira Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --el-font-size-base: 14px;
  --el-font-size-small: 13px;
  --el-font-size-large: 16px;
  --el-font-size-extra-large: 18px;
  
  /* Spacing (dense dashboard) */
  --el-border-radius-base: 6px;
  --el-border-radius-small: 4px;
  --el-border-radius-large: 8px;
  --el-border-radius-circle: 50%;
  
  /* Component sizes */
  --el-component-size: 32px;
  --el-component-size-small: 28px;
  --el-component-size-large: 36px;
}
```

Import in `main.ts`:

```typescript
import 'element-plus/dist/index.css'
import './styles/element-variables.css'
```

---

## Component Customization

### Tables (High Density)

```css
/* Dense ERP tables */
.el-table {
  --el-table-row-height: 36px;
  --el-table-header-height: 40px;
  --el-table-header-bg-color: #E9EEF6;
  --el-table-header-text-color: #1E3A8A;
  --el-table-border-color: #DBEAFE;
  --el-table-current-row-bg-color: #DBEAFE;
  --el-table-row-hover-bg-color: #E9EEF6;
  
  font-size: 14px;
}

.el-table thead th {
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-size: 13px;
}

.el-table .el-table__body-wrapper {
  scrollbar-width: thin;
}

/* Striped rows (optional) */
.el-table--striped .el-table__body tr.el-table__row--striped {
  background-color: #F8FAFC;
}

/* Selection column narrower */
.el-table .el-table-column--selection .cell {
  padding-left: 8px;
  padding-right: 8px;
}

/* Numeric columns */
.el-table .numeric-column {
  font-family: 'Fira Code', monospace;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
```

### Forms (Edit-Heavy Workflows)

```css
.el-form {
  --el-form-label-font-size: 13px;
}

.el-form-item {
  margin-bottom: 16px;
}

.el-form-item__label {
  font-weight: 500;
  color: var(--el-text-color-primary);
  padding-bottom: 4px;
}

/* Compact form layout */
.el-form.compact .el-form-item {
  margin-bottom: 12px;
}

/* Read-only fields */
.el-form-item.readonly .el-input__inner,
.el-form-item.readonly .el-textarea__inner {
  background-color: var(--el-fill-color-light);
  border-color: transparent;
  cursor: default;
}

/* Required asterisk styling */
.el-form-item.is-required:not(.is-no-asterisk) > .el-form-item__label::before {
  color: var(--el-color-danger);
  margin-right: 4px;
}

/* Inline validation */
.el-form-item.is-error .el-input__inner,
.el-form-item.is-error .el-textarea__inner,
.el-form-item.is-error .el-select .el-input__inner {
  border-color: var(--el-color-danger);
}

.el-form-item__error {
  font-size: 12px;
  line-height: 1.4;
  padding-top: 2px;
}
```

### Buttons (Manufacturing Context)

```css
/* Primary action (amber accent from MASTER.md) */
.el-button--primary {
  --el-button-bg-color: #D97706;
  --el-button-border-color: #D97706;
  --el-button-hover-bg-color: #F59E0B;
  --el-button-hover-border-color: #F59E0B;
  --el-button-active-bg-color: #B45309;
  --el-button-active-border-color: #B45309;
  
  font-weight: 600;
}

/* Secondary/outline */
.el-button--default {
  border-color: var(--el-border-color);
  font-weight: 500;
}

/* Danger actions */
.el-button--danger {
  font-weight: 600;
}

/* Compact size for toolbars */
.el-button.is-small {
  padding: 6px 12px;
  font-size: 13px;
}

/* Icon-only buttons */
.el-button.is-circle {
  padding: 8px;
}

/* Button group spacing */
.el-button-group .el-button {
  margin: 0;
}
```

### Tabs (Dossier Pattern)

```css
.el-tabs {
  --el-tabs-header-height: 48px;
}

.el-tabs__header {
  margin: 0;
  border-bottom: 1px solid var(--el-border-color);
}

.el-tabs__nav-wrap::after {
  display: none; /* Remove default border */
}

.el-tabs__item {
  padding: 0 20px;
  height: 48px;
  line-height: 48px;
  font-size: 15px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.el-tabs__item:hover {
  background-color: var(--el-fill-color-light);
}

.el-tabs__item.is-active {
  color: var(--el-color-primary);
  font-weight: 600;
}

.el-tabs__active-bar {
  height: 3px;
  background-color: var(--el-color-primary);
}

/* Modified indicator on tab (custom) */
.el-tabs__item.has-changes::after {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--el-color-warning);
  margin-left: 8px;
  vertical-align: middle;
}

.el-tabs__content {
  padding: 0; /* Let page content control padding */
}
```

### Dialogs & Drawers

```css
.el-dialog {
  border-radius: 6px;
  --el-dialog-padding-primary: 24px;
}

.el-dialog__header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.el-dialog__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.el-dialog__body {
  padding: 24px;
}

.el-dialog__footer {
  padding: 16px 24px;
  border-top: 1px solid var(--el-border-color-light);
}

/* Drawer for side panels */
.el-drawer {
  --el-drawer-padding-primary: 24px;
}

.el-drawer__header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--el-border-color-light);
  margin-bottom: 0;
}

.el-drawer__body {
  padding: 24px;
}
```

### Pagination (Compact)

```css
.el-pagination {
  --el-pagination-font-size: 14px;
  --el-pagination-bg-color: transparent;
  --el-pagination-hover-color: var(--el-color-primary);
  
  padding: 12px 0;
  justify-content: space-between;
}

.el-pagination .el-pager li {
  min-width: 28px;
  height: 28px;
  line-height: 28px;
  font-size: 13px;
  border-radius: 4px;
}

.el-pagination .el-pager li.is-active {
  background-color: var(--el-color-primary);
  color: white;
}

.el-pagination button {
  padding: 0 8px;
  min-width: 28px;
  height: 28px;
}

/* Show total */
.el-pagination .el-pagination__total {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
```

### Select & Dropdown (Improved UX)

```css
.el-select {
  width: 100%;
}

.el-select__wrapper {
  border-radius: 6px;
  transition: all 200ms ease;
}

.el-select__wrapper:hover {
  border-color: var(--el-color-primary-light-5);
}

.el-select__wrapper.is-focused {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

/* Dropdown panel */
.el-select-dropdown {
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.el-select-dropdown__item {
  padding: 8px 16px;
  font-size: 14px;
}

.el-select-dropdown__item.is-selected {
  color: var(--el-color-primary);
  font-weight: 600;
  background-color: var(--el-color-primary-light-9);
}

.el-select-dropdown__item.is-hovering {
  background-color: var(--el-fill-color-light);
}

/* Multiple select tags */
.el-select .el-select__tags .el-tag {
  border-radius: 4px;
  font-size: 12px;
  height: 24px;
  line-height: 24px;
}
```

### Input & Textarea

```css
.el-input__wrapper {
  border-radius: 6px;
  padding: 8px 12px;
  transition: all 200ms ease;
}

.el-input__wrapper:hover {
  border-color: var(--el-color-primary-light-5);
}

.el-input__wrapper.is-focus {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

.el-input__inner {
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.el-input__inner::placeholder {
  color: var(--el-text-color-placeholder);
}

/* Textarea */
.el-textarea__inner {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.5;
  font-family: var(--el-font-family);
}

.el-textarea__inner:focus {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

/* Prefix/suffix icons */
.el-input__prefix,
.el-input__suffix {
  color: var(--el-text-color-secondary);
}
```

### Loading & Progress

```css
/* Loading overlay */
.el-loading-mask {
  background-color: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(2px);
}

.el-loading-spinner .el-loading-text {
  color: var(--el-text-color-regular);
  font-size: 14px;
  margin-top: 8px;
}

/* Progress bars (for console KPIs) */
.el-progress {
  --el-progress-bg-color: var(--el-fill-color-light);
}

.el-progress__text {
  font-family: 'Fira Code', monospace;
  font-size: 14px !important;
  font-weight: 600;
}

.el-progress-bar__outer {
  border-radius: 4px;
}

.el-progress-bar__inner {
  border-radius: 4px;
}
```

### Notifications & Messages

```css
/* Notification (top-right alerts) */
.el-notification {
  border-radius: 8px;
  padding: 16px 20px;
  border-left: 4px solid var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.el-notification.el-notification--success {
  border-left-color: var(--el-color-success);
}

.el-notification.el-notification--warning {
  border-left-color: var(--el-color-warning);
}

.el-notification.el-notification--error {
  border-left-color: var(--el-color-danger);
}

.el-notification__title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.el-notification__content {
  font-size: 14px;
  line-height: 1.5;
}

/* Message (top-center banner) */
.el-message {
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.el-message__icon {
  font-size: 18px;
}
```

### Date Picker

```css
.el-date-editor {
  width: 100%;
}

.el-date-editor .el-input__wrapper {
  border-radius: 6px;
}

.el-picker-panel {
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.el-date-picker__header {
  margin: 12px;
}

.el-date-table td.available:hover {
  background-color: var(--el-color-primary-light-9);
}

.el-date-table td.today span {
  color: var(--el-color-primary);
  font-weight: 600;
}

.el-date-table td.current:not(.disabled) span {
  background-color: var(--el-color-primary);
  color: white;
}
```

---

## Utility Classes

```css
/* Spacing utilities (from dense spacing scale) */
.mb-xs { margin-bottom: 2px; }
.mb-sm { margin-bottom: 4px; }
.mb-md { margin-bottom: 8px; }
.mb-lg { margin-bottom: 12px; }
.mb-xl { margin-bottom: 16px; }
.mb-2xl { margin-bottom: 24px; }

.mt-xs { margin-top: 2px; }
.mt-sm { margin-top: 4px; }
.mt-md { margin-top: 8px; }
.mt-lg { margin-top: 12px; }
.mt-xl { margin-top: 16px; }
.mt-2xl { margin-top: 24px; }

.p-md { padding: 8px; }
.p-lg { padding: 12px; }
.p-xl { padding: 16px; }
.p-2xl { padding: 24px; }

/* Typography utilities */
.text-primary { color: var(--el-text-color-primary); }
.text-regular { color: var(--el-text-color-regular); }
.text-secondary { color: var(--el-text-color-secondary); }
.text-placeholder { color: var(--el-text-color-placeholder); }

.text-sm { font-size: 13px; }
.text-base { font-size: 14px; }
.text-lg { font-size: 16px; }
.text-xl { font-size: 18px; }

.font-normal { font-weight: 400; }
.font-medium { font-weight: 500; }
.font-semibold { font-weight: 600; }
.font-bold { font-weight: 700; }

.font-mono { font-family: 'Fira Code', monospace; }

/* Status badges */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-success {
  background: #D1FAE5;
  color: #065F46;
}

.badge-warning {
  background: #FEF3C7;
  color: #92400E;
}

.badge-error {
  background: #FEE2E2;
  color: #991B1B;
}

.badge-info {
  background: #E6E8EA;
  color: #334155;
}
```

---

## Dark Mode Support (Optional)

```css
[data-theme="dark"] {
  --el-bg-color: #0F172A;
  --el-bg-color-page: #0F172A;
  --el-bg-color-overlay: #1E293B;
  
  --el-text-color-primary: #F1F5F9;
  --el-text-color-regular: #CBD5E1;
  --el-text-color-secondary: #94A3B8;
  --el-text-color-placeholder: #64748B;
  
  --el-border-color: #334155;
  --el-border-color-light: #475569;
  --el-border-color-lighter: #475569;
  
  --el-fill-color: #1E293B;
  --el-fill-color-light: #334155;
  --el-fill-color-lighter: #475569;
  
  --el-table-header-bg-color: #1E293B;
  --el-table-row-hover-bg-color: #334155;
  --el-table-current-row-bg-color: #334155;
}

[data-theme="dark"] .el-table thead th {
  color: #F1F5F9;
}

[data-theme="dark"] .el-dialog,
[data-theme="dark"] .el-drawer {
  background-color: #1E293B;
}

[data-theme="dark"] .el-select-dropdown,
[data-theme="dark"] .el-picker-panel {
  background-color: #1E293B;
  border-color: #334155;
}
```

---

## Performance Optimization

### Tree-shaking (Vite config)

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
})
```

### Lazy loading large components

```typescript
// For data-heavy components like table
import { defineAsyncComponent } from 'vue'

const HeavyTable = defineAsyncComponent(() =>
  import('./components/HeavyTable.vue')
)
```

---

## Accessibility Enhancements

```css
/* Focus visible for keyboard navigation */
.el-button:focus-visible,
.el-input__wrapper:focus-visible,
.el-select__wrapper:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

/* High contrast for important actions */
.el-button--primary:focus-visible {
  outline-color: var(--el-color-warning);
}

/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

---

## Anti-Patterns

- ❌ Overriding `!important` extensively — Use CSS variable overrides
- ❌ Inline styles in templates — Use utility classes or scoped CSS
- ❌ Loading full Element Plus bundle — Use tree-shaking
- ❌ Custom components that duplicate Element Plus — Extend existing components
- ❌ Ignoring loading states — Always show spinners for async operations
