<template>
  <div class="login-page">
    <div class="logo-area">
      <h1>云端冲压</h1>
      <p>Cloud-Stamping ERP</p>
    </div>

    <van-form @submit="handleLogin">
      <van-cell-group inset>
        <van-field
          v-model="username"
          name="username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        />
        <van-field
          v-model="password"
          type="password"
          name="password"
          label="密码"
          placeholder="请输入密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        />
      </van-cell-group>
      <div class="submit-area">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          登录
        </van-button>
      </div>
    </van-form>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { getCurrentUser, login } from '@/api/auth'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

const handleLogin = async () => {
  loading.value = true
  try {
    const data = await login({ username: username.value, password: password.value })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    try {
      const user = await getCurrentUser()
      localStorage.setItem('mobile_user', JSON.stringify(user))
    } catch {
      localStorage.setItem('mobile_user', JSON.stringify({ username: username.value }))
    }
      showToast({ message: '登录成功', position: 'top' })
      router.push('/dashboard')
  } catch (error) {
    showToast({ message: '登录失败: ' + (error.message || '请检查账号密码'), position: 'top' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #10211f;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 20px;
}

.logo-area {
  text-align: center;
  margin-bottom: 40px;
  color: white;
}

.logo-area h1 {
  font-size: 32px;
  margin-bottom: 8px;
}

.logo-area p {
  font-size: 14px;
  opacity: 0.8;
}

.submit-area {
  margin: 24px 16px;
}

</style>
