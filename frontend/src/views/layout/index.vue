<template>
  <div class="layout">
    <el-container>
      <el-aside width="200px">
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/dashboard">
            <el-icon><DataBoard /></el-icon>
            <span>工作台</span>
          </el-menu-item>
          <el-menu-item index="/quotes">
            <el-icon><Document /></el-icon>
            <span>报价管理</span>
          </el-menu-item>
          <el-menu-item index="/parts">
            <el-icon><Box /></el-icon>
            <span>零件管理</span>
          </el-menu-item>
          <el-menu-item index="/customers">
            <el-icon><User /></el-icon>
            <span>客户管理</span>
          </el-menu-item>
          <el-menu-item
            v-if="userStore.userInfo?.role_level >= 4"
            index="/dictionary"
          >
            <el-icon><Setting /></el-icon>
            <span>字典管理</span>
          </el-menu-item>
          <el-menu-item index="/production">
            <el-icon><Grid /></el-icon>
            <span>生产计划</span>
          </el-menu-item>
          <el-menu-item index="/machines">
            <el-icon><Cpu /></el-icon>
            <span>机台管理</span>
          </el-menu-item>
          <el-menu-item index="/sampling">
            <el-icon><Aim /></el-icon>
            <span>打样管理</span>
          </el-menu-item>
          <el-menu-item index="/tooling">
            <el-icon><Tools /></el-icon>
            <span>模具管理</span>
          </el-menu-item>
          <el-menu-item index="/warehouse">
            <el-icon><House /></el-icon>
            <span>仓库</span>
          </el-menu-item>
          <el-menu-item index="/materials">
            <el-icon><Goods /></el-icon>
            <span>原材料管理</span>
          </el-menu-item>
          <el-menu-item index="/packaging">
            <el-icon><TakeawayBox /></el-icon>
            <span>包装管理</span>
          </el-menu-item>
          <el-menu-item index="/quality">
            <el-icon><CircleCheck /></el-icon>
            <span>质量管控</span>
          </el-menu-item>
          <el-menu-item index="/coating/recipes">
            <el-icon><Brush /></el-icon>
            <span>喷涂管理</span>
          </el-menu-item>
          <el-menu-item
            v-if="userStore.userInfo?.role_level >= 10"
            index="/admin/context-switch"
          >
            <el-icon><SwitchFilled /></el-icon>
            <span>视角切换</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-content">
            <h3>Zephyr ERP</h3>
            <el-dropdown @command="handleCommand">
              <span class="user-info">
                {{ userStore.userInfo?.real_name || '用户' }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item
                    v-if="userStore.userInfo?.role_level >= 10"
                    command="context-switch"
                  >视角切换</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeMenu = computed(() => route.path)

const handleCommand = (command: string) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (command === 'context-switch') {
    router.push('/admin/context-switch')
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
}

.el-aside {
  background-color: #304156;
}

.el-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.el-main {
  background-color: #f0f2f5;
  padding: 16px;
}
</style>
