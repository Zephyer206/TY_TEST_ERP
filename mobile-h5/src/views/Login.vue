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

    <div class="server-info">
      <p>服务器: {{ serverUrl }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const serverUrl = ref('http://124.222.29.229:8000')

const handleLogin = async () => {
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('username', username.value)
    formData.append('password', password.value)

    const response = await fetch(`${serverUrl.value}/login`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })

    if (response.redirected || response.url.includes('/login') === false) {
      // 保存用户信息到 localStorage
      localStorage.setItem('user_id', 'logged_in')
      localStorage.setItem('server_url', serverUrl.value)
      localStorage.setItem('username', username.value)
      showToast({ message: '登录成功', position: 'top' })
      router.push('/dashboard')
    } else {
      showToast({ message: '用户名或密码错误', position: 'top' })
    }
  } catch (error) {
    showToast({ message: '登录失败: ' + error.message, position: 'top' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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

.server-info {
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  margin-top: 20px;
}
</style>
