# Responsive Behavior

> **Strategy:** Desktop-first with graceful mobile degradation
> **Primary Target:** 1440px+ desktop (manufacturing workstations)
> **Secondary Target:** 1024px+ tablets (shop floor supervision)
> **Tertiary Target:** <768px mobile emergency access only

---

**Generated:** 2026-08-07
**Breakpoints:** Element Plus defaults + custom refinements

---

## Breakpoint System

### Standard Breakpoints

```css
/* Element Plus breakpoints (match these) */
:root {
  --breakpoint-xs: 0px;      /* Mobile portrait */
  --breakpoint-sm: 768px;    /* Tablet portrait */
  --breakpoint-md: 992px;    /* Tablet landscape */
  --breakpoint-lg: 1200px;   /* Desktop */
  --breakpoint-xl: 1920px;   /* Large desktop */
}
```

### Media Query Mixins (SCSS)

```scss
@mixin respond-to($breakpoint) {
  @if $breakpoint == 'mobile' {
    @media (max-width: 767px) { @content; }
  }
  @else if $breakpoint == 'tablet' {
    @media (min-width: 768px) and (max-width: 991px) { @content; }
  }
  @else if $breakpoint == 'desktop' {
    @media (min-width: 992px) { @content; }
  }
  @else if $breakpoint == 'wide' {
    @media (min-width: 1440px) { @content; }
  }
}

// Usage
.data-grid {
  grid-template-columns: repeat(3, 1fr);
  
  @include respond-to('tablet') {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @include respond-to('mobile') {
    grid-template-columns: 1fr;
  }
}
```

---

## Layout Patterns by Breakpoint

### Desktop (≥ 1200px) — Primary Target

**Navigation:**
- Horizontal top bar with full domain labels
- Secondary navigation visible below
- Sidebar panels at 280-320px width

**Content:**
- Multi-column layouts (2-4 columns)
- Full data tables with all columns
- Side-by-side forms (2-3 columns)
- Inspector panels visible

**Console:**
- Three-column grid (sidebar + main + inspector)
- Full hierarchical tables with indentation
- Real-time charts at full width

```css
.page-layout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 0;
  height: 100vh;
}
```

---

### Tablet Landscape (992px - 1199px)

**Navigation:**
- Horizontal top bar with abbreviated domain labels
- Secondary navigation collapsible or dropdown
- No persistent sidebar (use drawer on demand)

**Content:**
- 2-column layouts
- Tables with column picker (hide non-essential columns)
- Single-column forms
- Inspector as overlay drawer

**Console:**
- Two-column grid (main + collapsible inspector)
- Sidebar becomes drawer overlay
- Simplified hierarchical display (1 level only)

```css
@media (max-width: 1199px) {
  .page-layout {
    grid-template-columns: 1fr 320px;
  }
  
  .console-sidebar {
    position: fixed;
    left: -280px;
    transition: left 300ms ease;
    z-index: 200;
  }
  
  .console-sidebar.open {
    left: 0;
  }
}
```

---

### Tablet Portrait (768px - 991px)

**Navigation:**
- Horizontal top bar with icon + short labels
- Secondary navigation as dropdown menu
- Hamburger menu for less-used features

**Content:**
- Single-column layouts
- Tables with horizontal scroll (sticky first column)
- Stack form fields vertically
- Inspector as full-screen modal

**Console:**
- Single column with tabbed sections
- Status cards in 2-column grid
- Charts stack vertically
- No persistent panels

```css
@media (max-width: 991px) {
  .page-layout {
    grid-template-columns: 1fr;
  }
  
  .data-table-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  
  .data-table thead th:first-child,
  .data-table tbody td:first-child {
    position: sticky;
    left: 0;
    background: var(--color-background);
    z-index: 10;
  }
  
  .form-grid {
    grid-template-columns: 1fr !important;
  }
}
```

---

### Mobile (< 768px) — Emergency Access Only

**Navigation:**
- Bottom tab bar (4 domains)
- Top bar with app logo + menu button
- Full-screen drawer for secondary nav

**Content:**
- Card-based lists (no tables)
- Single-column forms with larger inputs
- Modals become full-screen views
- No inspector or side panels

**Console:**
- Simplified KPI cards only
- Status list view (no hierarchy)
- Charts not shown (link to desktop)
- Emergency alerts prominent

```css
@media (max-width: 767px) {
  /* Bottom navigation */
  .primary-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    flex-direction: row;
    justify-content: space-around;
    height: 64px;
    z-index: 1000;
  }
  
  /* Card-based list instead of table */
  .parts-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .part-card {
    padding: 16px;
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 8px;
  }
  
  /* Full-screen modals */
  .el-dialog {
    width: 100vw !important;
    height: 100vh !important;
    margin: 0 !important;
    border-radius: 0 !important;
  }
  
  /* Larger touch targets */
  .el-button {
    min-height: 44px;
    padding: 12px 20px;
  }
  
  .el-input__inner {
    font-size: 16px; /* Prevents iOS zoom */
    min-height: 44px;
  }
}
```

---

## Component Responsiveness

### Parts List

| Breakpoint | Layout | Columns Visible | Actions |
|------------|--------|-----------------|---------|
| ≥ 1200px | Table | 12-14 | Inline buttons |
| 992-1199px | Table | 8-10 | Dropdown menu |
| 768-991px | Table (scroll) | 6 (sticky first) | Icon buttons |
| < 768px | Card list | All (stacked) | Bottom sheet |

**Implementation:**
```vue
<template>
  <div class="parts-list-container">
    <!-- Desktop/Tablet: Table -->
    <el-table 
      v-if="!isMobile"
      :data="parts"
      class="parts-table"
    >
      <el-table-column prop="partNumber" label="Part Number" fixed />
      <el-table-column prop="name" label="Name" />
      <el-table-column prop="category" label="Category" v-if="isDesktop" />
      <el-table-column prop="material" label="Material" v-if="isWide" />
      <!-- More columns... -->
    </el-table>
    
    <!-- Mobile: Card list -->
    <div v-else class="parts-cards">
      <div v-for="part in parts" :key="part.id" class="part-card">
        <h3>{{ part.partNumber }}</h3>
        <p>{{ part.name }}</p>
        <div class="part-meta">
          <span>{{ part.category }}</span>
          <span>{{ part.material }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBreakpoints } from '@/composables/useBreakpoints'

const { isMobile, isDesktop, isWide } = useBreakpoints()
</script>
```

### Part Detail (Dossier)

| Breakpoint | Tab Layout | Form Columns | Actions |
|------------|------------|--------------|---------|
| ≥ 1200px | Horizontal tabs | 3 columns | Right sidebar |
| 992-1199px | Horizontal tabs | 2 columns | Sticky footer |
| 768-991px | Horizontal tabs | 1 column | Sticky footer |
| < 768px | Dropdown selector | 1 column | Fixed bottom |

### Manufacturing Console

| Breakpoint | Layout | Panels | Update Freq |
|------------|--------|--------|-------------|
| ≥ 1200px | 3-column grid | All visible | Real-time |
| 992-1199px | 2-column + drawer | Main + inspector | 10 sec |
| 768-991px | Tabs | Tabbed sections | 30 sec |
| < 768px | KPIs only | Simplified | Manual refresh |

---

## Responsive Typography

```css
:root {
  --font-size-h1: clamp(24px, 4vw, 32px);
  --font-size-h2: clamp(20px, 3vw, 24px);
  --font-size-h3: clamp(16px, 2.5vw, 20px);
  --font-size-body: clamp(14px, 1.5vw, 16px);
  --font-size-small: clamp(12px, 1.2vw, 14px);
}

h1 { font-size: var(--font-size-h1); }
h2 { font-size: var(--font-size-h2); }
h3 { font-size: var(--font-size-h3); }
body { font-size: var(--font-size-body); }
.text-small { font-size: var(--font-size-small); }
```

---

## Responsive Spacing

```css
.section {
  padding: clamp(16px, 4vw, 48px);
}

.card {
  padding: clamp(12px, 2vw, 24px);
}

.grid {
  gap: clamp(12px, 2vw, 24px);
}
```

---

## Element Plus Responsive Utilities

### Grid Layout

```vue
<el-row :gutter="16">
  <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
    <!-- Column content -->
  </el-col>
</el-row>
```

### Hidden Classes

```vue
<!-- Hide on mobile -->
<div class="hidden-xs-only">Desktop/Tablet content</div>

<!-- Show only on mobile -->
<div class="hidden-sm-and-up">Mobile content</div>

<!-- Hide on desktop -->
<div class="hidden-md-and-up">Mobile/Tablet content</div>
```

---

## Image & Media Responsiveness

```html
<!-- Responsive images -->
<img 
  :src="imageSrc"
  :srcset="`
    ${imageSrc}?w=320 320w,
    ${imageSrc}?w=640 640w,
    ${imageSrc}?w=1024 1024w,
    ${imageSrc}?w=1920 1920w
  `"
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
  alt="Part diagram"
  loading="lazy"
/>

<!-- Responsive video -->
<div class="video-container">
  <video 
    controls
    :poster="posterUrl"
    preload="metadata"
  >
    <source src="/video-mobile.mp4" type="video/mp4" media="(max-width: 767px)">
    <source src="/video-desktop.mp4" type="video/mp4">
  </video>
</div>

<style>
.video-container {
  position: relative;
  padding-bottom: 56.25%; /* 16:9 aspect ratio */
  height: 0;
  overflow: hidden;
}

.video-container video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}
</style>
```

---

## Performance Considerations

**Conditional rendering for mobile:**
```vue
<template>
  <!-- Desktop: render full hierarchy -->
  <div v-if="isDesktop" class="hierarchy-table">
    <HierarchicalTable :data="complexData" />
  </div>
  
  <!-- Mobile: render simplified list -->
  <div v-else class="simple-list">
    <SimpleList :data="simplifiedData" />
  </div>
</template>
```

**Lazy loading images:**
```vue
<template>
  <img
    v-if="isVisible"
    :src="imageSrc"
    loading="lazy"
    alt="Part photo"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'

const target = ref(null)
const isVisible = ref(false)

useIntersectionObserver(
  target,
  ([{ isIntersecting }]) => {
    if (isIntersecting) {
      isVisible.value = true
    }
  }
)
</script>
```

---

## Testing Checklist

- [ ] Test at 320px width (iPhone SE)
- [ ] Test at 768px (iPad portrait)
- [ ] Test at 1024px (iPad landscape)
- [ ] Test at 1440px (standard desktop)
- [ ] Test at 1920px (large desktop)
- [ ] Test with browser zoom at 200%
- [ ] Test orientation changes (portrait ↔ landscape)
- [ ] Test with touch events on tablet
- [ ] Verify no page-level horizontal scroll; a constrained data-table wrapper may scroll at tablet widths with the first column fixed
- [ ] Check fixed elements don't overlap content

---

## Anti-Patterns

- ❌ Horizontal scroll on mobile (except data tables)
- ❌ Fixed pixel widths without max-width
- ❌ Disabling viewport zoom (`user-scalable=no`)
- ❌ Assuming mobile = touch (use hover media query)
- ❌ Hiding critical features on mobile
- ❌ Tiny touch targets (< 44×44px)
- ❌ Modal dialogs that exceed viewport height
- ❌ Desktop-only layouts with no mobile fallback
