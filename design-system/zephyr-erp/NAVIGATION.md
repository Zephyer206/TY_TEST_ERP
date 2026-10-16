# Navigation Structure

> **Consolidation:** Single unified navigation replacing fragmented sidebar

---

**Generated:** 2026-08-07
**Philosophy:** Odoo-inspired information architecture — four primary domains, minimal depth

---

## Primary Navigation

### Four Core Domains

```
┌─────────────────────────────────────────────────────────────┐
│  [产品]  [工艺与生产]  [库存]  [客户与报价]                  │
└─────────────────────────────────────────────────────────────┘
```

**No more:**
- Scattered sidebar entries
- Unclear groupings
- Deep nesting (3+ levels)
- Redundant menu items

---

## Domain 1: 产品 (Products)

**Purpose:** Part catalog, specifications, relationships

**Top-level menu items:**
- 零件列表 (Parts List)
- 材料管理 (Materials)
- 产品分类 (Categories)
- 零件关系 (Part Relations)

**Typical user flow:**
1. Browse parts list (list-first archetype)
2. Click part → Detail view (dossier-first archetype)
3. Navigate to related parts/materials via tabs
4. Return to list (browser back or breadcrumb)

**URL structure:**
```
/products/parts
/products/parts/:id
/products/materials
/products/materials/:id
/products/categories
```

---

## Domain 2: 工艺与生产 (Process & Production)

**Purpose:** Manufacturing operations, tooling, production control

**Top-level menu items:**
- 生产控制台 (Production Console) ← manufacturing-console archetype
- 工艺路线 (Process Routes)
- 模具管理 (Mold Management)
- 工装配置 (Tooling Configuration)
- 生产订单 (Production Orders)

**Console as landing page:**
- Default route for production users
- Real-time status monitoring
- Quick access to active orders
- Equipment status overview

**URL structure:**
```
/production/console
/production/routes
/production/routes/:id
/production/molds
/production/molds/:id
/production/tooling
/production/orders
/production/orders/:id
```

---

## Domain 3: 库存 (Inventory)

**Purpose:** Stock levels, warehouse management, material tracking

**Top-level menu items:**
- 库存总览 (Inventory Overview)
- 入库管理 (Inbound)
- 出库管理 (Outbound)
- 库存调整 (Adjustments)
- 盘点记录 (Stock Counts)

**URL structure:**
```
/inventory/overview
/inventory/inbound
/inventory/outbound
/inventory/adjustments
/inventory/counts
```

---

## Domain 4: 客户与报价 (Customers & Quotations)

**Purpose:** Customer relationships, pricing, order management

**Top-level menu items:**
- 客户列表 (Customers)
- 报价管理 (Quotations)
- 价格管理 (Pricing)
- 客户件号 (Customer Part Numbers)
- 订单历史 (Order History)

**URL structure:**
```
/customers
/customers/:id
/quotations
/quotations/:id
/pricing
/orders
```

---

## Navigation Component Spec

### Top Bar (Primary Nav)

```vue
<template>
  <nav class="primary-nav">
    <div class="nav-brand">
      <img src="/logo.svg" alt="Zephyr ERP" />
      <span class="nav-title">Zephyr ERP</span>
    </div>
    
    <div class="nav-domains">
      <el-menu
        mode="horizontal"
        :default-active="activeRoute"
        :router="true"
      >
        <el-menu-item index="/products">产品</el-menu-item>
        <el-menu-item index="/production">工艺与生产</el-menu-item>
        <el-menu-item index="/inventory">库存</el-menu-item>
        <el-menu-item index="/customers">客户与报价</el-menu-item>
      </el-menu>
    </div>
    
    <div class="nav-actions">
      <el-button circle icon="Search" />
      <el-button circle icon="Bell" />
      <el-dropdown>
        <el-avatar :size="32">Admin</el-avatar>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-menu-item>个人设置</el-dropdown-menu-item>
            <el-dropdown-menu-item>系统设置</el-dropdown-menu-item>
            <el-dropdown-menu-item divided>退出登录</el-dropdown-menu-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </nav>
</template>

<style scoped>
.primary-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 24px;
  background: white;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-brand img {
  height: 32px;
}

.nav-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-foreground);
}

.nav-domains {
  flex: 1;
  display: flex;
  justify-content: center;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Element Plus overrides */
.nav-domains :deep(.el-menu) {
  border: none;
  background: transparent;
}

.nav-domains :deep(.el-menu-item) {
  font-size: 15px;
  font-weight: 500;
  padding: 0 20px;
  height: 60px;
  line-height: 60px;
  border-bottom: 3px solid transparent;
}

.nav-domains :deep(.el-menu-item:hover) {
  background: var(--color-muted);
}

.nav-domains :deep(.el-menu-item.is-active) {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: transparent;
}
</style>
```

### Secondary Nav (Domain Submenu)

```vue
<template>
  <div class="secondary-nav" v-if="currentDomain">
    <el-menu
      mode="horizontal"
      :default-active="activeSubRoute"
      :router="true"
    >
      <el-menu-item
        v-for="item in domainMenuItems"
        :key="item.path"
        :index="item.path"
      >
        {{ item.label }}
      </el-menu-item>
    </el-menu>
  </div>
</template>

<style scoped>
.secondary-nav {
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  padding: 0 24px;
}

.secondary-nav :deep(.el-menu) {
  border: none;
  background: transparent;
}

.secondary-nav :deep(.el-menu-item) {
  font-size: 14px;
  padding: 0 16px;
  height: 44px;
  line-height: 44px;
  color: var(--color-foreground);
}

.secondary-nav :deep(.el-menu-item.is-active) {
  color: var(--color-primary);
  font-weight: 600;
  border-bottom: 2px solid var(--color-primary);
}
</style>
```

---

## Breadcrumb Navigation

**Show breadcrumbs for:**
- Detail views (Parts detail, Order detail, etc.)
- Nested configuration pages
- Multi-step wizards

**Don't show breadcrumbs for:**
- Top-level list views (redundant with secondary nav)
- Dashboard/console views

```vue
<template>
  <el-breadcrumb separator="/" class="page-breadcrumb">
    <el-breadcrumb-item :to="{ path: '/products' }">产品</el-breadcrumb-item>
    <el-breadcrumb-item :to="{ path: '/products/parts' }">零件列表</el-breadcrumb-item>
    <el-breadcrumb-item>{{ currentPartNumber }}</el-breadcrumb-item>
  </el-breadcrumb>
</template>

<style scoped>
.page-breadcrumb {
  padding: 12px 24px;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  font-size: 14px;
}
</style>
```

---

## Search (Global)

**Trigger:** Click search icon in top bar, or press `/` keyboard shortcut

**Search scope:**
- Parts (by part number, name, customer part number)
- Customers
- Orders
- Molds
- Materials

**UI:** Full-screen overlay with centered search input

```vue
<template>
  <el-dialog
    v-model="searchVisible"
    :show-close="false"
    :modal="true"
    width="600px"
    align-center
    class="search-dialog"
  >
    <el-input
      v-model="searchQuery"
      placeholder="搜索零件、客户、订单..."
      size="large"
      clearable
      @input="handleSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>
    
    <div class="search-results" v-if="searchResults.length">
      <div
        v-for="result in searchResults"
        :key="result.id"
        class="search-result-item"
        @click="navigateToResult(result)"
      >
        <div class="result-type">{{ result.type }}</div>
        <div class="result-title">{{ result.title }}</div>
        <div class="result-subtitle">{{ result.subtitle }}</div>
      </div>
    </div>
    
    <div class="search-shortcuts">
      <kbd>↑</kbd><kbd>↓</kbd> 导航 · <kbd>Enter</kbd> 选择 · <kbd>Esc</kbd> 关闭
    </div>
  </el-dialog>
</template>

<style scoped>
.search-dialog :deep(.el-dialog) {
  background: white;
  border-radius: 12px;
  box-shadow: var(--shadow-xl);
}

.search-results {
  margin-top: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.search-result-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 150ms ease;
}

.search-result-item:hover {
  background: var(--color-muted);
}

.result-type {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.result-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 2px;
}

.result-subtitle {
  font-size: 13px;
  color: #6B7280;
}

.search-shortcuts {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 13px;
  color: #6B7280;
  text-align: center;
}

.search-shortcuts kbd {
  padding: 2px 6px;
  background: var(--color-muted);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  margin: 0 2px;
}
</style>
```

---

## Mobile Navigation (< 768px)

**Pattern:** Bottom tab bar for primary domains

```vue
<template>
  <div class="mobile-nav">
    <router-link
      v-for="domain in domains"
      :key="domain.path"
      :to="domain.path"
      class="mobile-nav-item"
      :class="{ active: isActive(domain.path) }"
    >
      <el-icon :size="24">
        <component :is="domain.icon" />
      </el-icon>
      <span>{{ domain.label }}</span>
    </router-link>
  </div>
</template>

<style scoped>
.mobile-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  background: white;
  border-top: 1px solid var(--color-border);
  padding: 8px 0;
  z-index: 100;
}

.mobile-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  text-decoration: none;
  color: #6B7280;
  transition: color 150ms ease;
}

.mobile-nav-item span {
  font-size: 11px;
}

.mobile-nav-item.active {
  color: var(--color-primary);
  font-weight: 600;
}
</style>
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Open global search |
| `G + P` | Go to Products |
| `G + M` | Go to Production (Manufacturing) |
| `G + I` | Go to Inventory |
| `G + C` | Go to Customers |
| `Ctrl + K` | Command palette (future) |
| `Esc` | Close modal/drawer/search |

---

## Route Guards & Permissions

**Implementation note:** Use Vue Router navigation guards

```typescript
router.beforeEach((to, from, next) => {
  // Check if user has permission for this domain
  const domain = to.path.split('/')[1]
  const userPermissions = store.state.user.permissions
  
  if (requiresAuth(to) && !isAuthenticated()) {
    next('/login')
  } else if (!hasPermission(userPermissions, domain)) {
    next('/forbidden')
  } else {
    next()
  }
})
```

**Permission levels:**
- View: Read-only access
- Edit: Can modify records
- Create: Can create new records
- Delete: Can delete records
- Admin: Full domain access

---

## Anti-Patterns

- ❌ Nested dropdowns (2+ levels) — Use secondary nav instead
- ❌ "Hamburger menu" on desktop — Wastes horizontal space
- ❌ Auto-collapsing sidebar — Causes layout shift
- ❌ Unlabeled icon-only nav items — Fails accessibility
- ❌ External links in primary nav — Use footer or settings
- ❌ More than 6 primary domains — Violates cognitive load limits
