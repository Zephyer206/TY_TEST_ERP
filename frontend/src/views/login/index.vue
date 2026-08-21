<template>
  <main class="login-page">
    <div class="grid-motif" aria-hidden="true"></div>
    <div class="accent-line accent-line-top" aria-hidden="true"></div>
    <div class="accent-line accent-line-bottom" aria-hidden="true"></div>

    <section class="login-surface" aria-labelledby="login-title">
      <div class="brand-panel">
        <div class="brand-lockup" aria-label="Zephyr ERP">
          <span class="brand-mark">Z</span>
          <span class="brand-name">Zephyr ERP</span>
        </div>

        <div class="brand-copy">
          <p class="eyebrow">Manufacturing workspace</p>
          <h1>把零件、工装与生产，放在同一条线上。</h1>
          <p class="brand-description">
            从产品参数查询，到制造执行、物料协同与交付作业，进入统一的制造工作台。
          </p>
        </div>

        <svg class="process-motif" viewBox="0 0 440 220" fill="none" aria-hidden="true">
          <path d="M18 174H96L126 144H202L232 114H308L338 84H422" stroke="currentColor" stroke-width="1.5" />
          <path d="M18 198H116L148 166H224L256 134H332L364 102H422" stroke="currentColor" stroke-width="1" opacity=".45" />
          <circle cx="96" cy="174" r="5" fill="currentColor" />
          <circle cx="202" cy="114" r="5" fill="currentColor" />
          <circle cx="308" cy="84" r="5" fill="currentColor" />
          <path d="M96 174V208M202 114V148M308 84V118" stroke="currentColor" stroke-width="1" opacity=".35" />
          <path d="M76 208H116M182 148H222M288 118H328" stroke="currentColor" stroke-width="1" opacity=".35" />
        </svg>

        <p class="trust-line">授权用户登录 · 数据访问按角色控制</p>
      </div>

      <div class="form-panel">
        <div class="form-heading">
          <p class="section-kicker">Welcome back</p>
          <h2 id="login-title">登录 Zephyr ERP</h2>
          <p>继续处理今天的制造任务。</p>
        </div>

        <el-form
          ref="formRef"
          class="login-form"
          :model="form"
          :rules="rules"
          label-position="top"
          hide-required-asterisk
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username" label="用户名">
            <el-input
              v-model="form.username"
              name="username"
              autocomplete="username"
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="User"
              aria-label="用户名"
            />
          </el-form-item>

          <el-form-item prop="password" label="密码">
            <el-input
              v-model="form.password"
              name="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              size="large"
              :type="passwordVisible ? 'text' : 'password'"
              :prefix-icon="Lock"
              aria-label="密码"
              @keyup.enter="handleLogin"
            >
              <template #suffix>
                <button
                  type="button"
                  class="password-toggle"
                  :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
                  :aria-pressed="passwordVisible"
                  @click="passwordVisible = !passwordVisible"
                >
                  <el-icon aria-hidden="true">
                    <Hide v-if="passwordVisible" />
                    <View v-else />
                  </el-icon>
                </button>
              </template>
            </el-input>
          </el-form-item>

          <el-button
            class="login-submit"
            type="primary"
            native-type="submit"
            :loading="loading"
          >
            {{ loading ? '登录中…' : '登录' }}
            <el-icon v-if="!loading" aria-hidden="true"><ArrowRight /></el-icon>
          </el-button>
        </el-form>

        <p class="form-footnote">首次使用或无法登录时，请联系系统管理员。</p>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ArrowRight, Hide, Lock, User, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const passwordVisible = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const handleLogin = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    userStore.setToken(data.access_token)

    userStore.setUserInfo({
      id: 1,
      username: form.username,
      real_name: form.username === 'admin' ? '管理员' : form.username,
      role_level: 4,
      dept: 'prod',
      is_tech: false,
    })

    ElMessage.success('登录成功')
    setTimeout(() => router.push('/parts'), 100)
  } catch (error) {
    console.error('登录错误:', error)
    ElMessage.error('登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  display: grid;
  min-height: 100vh;
  place-items: center;
  overflow: hidden;
  padding: 24px;
  color: #edf5f2;
  background: #0b1718;
}

.grid-motif {
  position: absolute;
  inset: 0;
  opacity: .3;
  background-image:
    linear-gradient(rgba(169, 216, 202, .055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(169, 216, 202, .055) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent 0%, #000 28%, #000 72%, transparent 100%);
}

.accent-line {
  position: absolute;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(93, 194, 164, .8), transparent);
  opacity: .7;
}

.accent-line-top { top: 18%; left: 0; width: 38%; }
.accent-line-bottom { right: 0; bottom: 16%; width: 30%; opacity: .4; }

.login-surface {
  position: relative;
  z-index: 1;
  display: grid;
  width: min(1000px, 100%);
  min-height: 528px;
  grid-template-columns: minmax(0, 1fr) 380px;
  overflow: hidden;
  border: 1px solid rgba(211, 239, 230, .2);
  border-radius: 18px;
  background: rgba(19, 38, 37, .68);
  box-shadow: 0 30px 80px rgba(0, 0, 0, .38), 0 5px 18px rgba(0, 0, 0, .22);
  backdrop-filter: blur(24px) saturate(120%);
}

.brand-panel {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: space-between;
  padding: 36px 42px 28px;
  border-right: 1px solid rgba(211, 239, 230, .12);
  background: linear-gradient(145deg, rgba(25, 60, 55, .52), rgba(12, 27, 28, .18));
}

.brand-lockup { display: inline-flex; align-items: center; gap: 10px; }
.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 7px;
  color: #12332d;
  background: #dceee8;
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -.05em;
}
.brand-name { color: #f5fbf8; font-size: 18px; font-weight: 650; letter-spacing: -.02em; }

.brand-copy { max-width: 410px; margin: auto 0; padding: 34px 0 24px; }
.eyebrow, .section-kicker {
  margin: 0 0 16px;
  color: #72c6ae;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
  line-height: 1.4;
  text-transform: uppercase;
}
.brand-copy h1 {
  max-width: 390px;
  margin: 0;
  color: #f2f8f5;
  font-size: clamp(30px, 3.6vw, 44px);
  font-weight: 650;
  letter-spacing: -.045em;
  line-height: 1.08;
}
.brand-description { max-width: 360px; margin: 18px 0 0; color: rgba(224, 240, 234, .7); font-size: 14px; line-height: 1.65; }

.process-motif { position: absolute; right: 28px; bottom: 58px; width: min(54%, 440px); color: rgba(93, 194, 164, .34); }
.trust-line { margin: 0; color: rgba(222, 239, 232, .52); font-size: 12px; }

.form-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40px 36px 36px;
  background: rgba(245, 251, 248, .065);
}
.form-heading { margin-bottom: 24px; }
.form-heading .section-kicker { margin-bottom: 10px; }
.form-heading h2 { margin: 0; color: #f4fbf8; font-size: 28px; font-weight: 650; letter-spacing: -.04em; line-height: 1.15; }
.form-heading p:last-child { margin: 8px 0 0; color: rgba(220, 239, 231, .62); font-size: 13px; }
.login-form { width: 100%; }
.login-form :deep(.el-form-item) { margin-bottom: 15px; }
.login-form :deep(.el-form-item.is-error) { margin-bottom: 24px; }
.login-form :deep(.el-form-item__label) { height: auto; margin-bottom: 6px; padding: 0; color: rgba(227, 242, 236, .78); font-size: 12px; line-height: 1.4; }
.login-form :deep(.el-input__wrapper) {
  min-height: 44px;
  border: 1px solid rgba(214, 239, 230, .16);
  border-radius: 8px;
  background: rgba(7, 19, 19, .56);
  box-shadow: none;
  transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
}
.login-form :deep(.el-input__wrapper:hover) { border-color: rgba(171, 226, 210, .38); }
.login-form :deep(.el-input__wrapper.is-focus) { border-color: #6fcaad; background: rgba(7, 19, 19, .74); box-shadow: 0 0 0 3px rgba(111, 202, 173, .16); }
.login-form :deep(.el-input__inner) { color: #f4fbf8; font-size: 16px; }
.login-form :deep(.el-input__inner::placeholder) { color: rgba(205, 226, 218, .38); }
.login-form :deep(.el-input__inner:-webkit-autofill),
.login-form :deep(.el-input__inner:-webkit-autofill:hover),
.login-form :deep(.el-input__inner:-webkit-autofill:focus) {
  -webkit-text-fill-color: #f4fbf8;
  -webkit-box-shadow: 0 0 0 1000px rgba(7, 19, 19, .56) inset;
  box-shadow: 0 0 0 1000px rgba(7, 19, 19, .56) inset;
  caret-color: #f4fbf8;
  transition: background-color 9999s ease-out;
}
.login-form :deep(.el-input__prefix-inner), .login-form :deep(.el-input__suffix-inner) { color: rgba(166, 216, 201, .68); }
.password-toggle {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  margin-right: -4px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  color: rgba(166, 216, 201, .7);
  background: transparent;
  cursor: pointer;
}
.password-toggle:hover { color: #b9efdc; background: rgba(145, 221, 194, .1); }
.password-toggle:focus-visible { outline: 2px solid #91ddc2; outline-offset: 2px; }
.login-form :deep(.el-form-item__error) { padding-top: 6px; color: #ffb8ad; font-size: 12px; line-height: 1.4; }

.login-submit {
  width: 100%;
  min-height: 44px;
  margin-top: 4px;
  border: 1px solid rgba(169, 239, 214, .48);
  border-radius: 8px;
  color: #0c2720;
  background: #91ddc2;
  box-shadow: 0 8px 18px rgba(63, 177, 143, .2);
  font-size: 14px;
  font-weight: 700;
  transition: background-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}
.login-submit:hover { border-color: #b4f0dd; color: #0a201a; background: #abebd3; box-shadow: 0 11px 24px rgba(63, 177, 143, .28); }
.login-submit:active { transform: translateY(1px); }
.login-submit .el-icon { margin-left: 7px; }
.form-footnote { margin: 20px 0 0; color: rgba(220, 239, 231, .46); font-size: 12px; line-height: 1.6; }

@media (max-width: 760px) {
  .login-page { padding: 18px; }
  .login-surface { display: block; min-height: 0; max-width: 430px; }
  .brand-panel { min-height: 188px; padding: 25px 26px 23px; border-right: 0; border-bottom: 1px solid rgba(211, 239, 230, .12); }
  .brand-copy { margin: 30px 0 0; padding: 0; }
  .brand-copy h1 { max-width: 330px; font-size: 30px; }
  .brand-description, .process-motif { display: none; }
  .trust-line { margin-top: 24px; }
  .form-panel { padding: 34px 26px 30px; }
}

@media (max-width: 390px) {
  .login-page { padding: 12px; }
  .brand-panel { padding: 22px 20px; }
  .form-panel { padding: 30px 20px 24px; }
  .form-heading h2 { font-size: 27px; }
}

@media (prefers-reduced-motion: reduce) {
  .login-form :deep(.el-input__wrapper), .login-submit { transition: none; }
}
</style>
