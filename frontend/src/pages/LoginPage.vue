<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { useChatStore } from '@/stores/useChatStore'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const chat = useChatStore()

const username = ref('user_a')
const password = ref('usera123')

async function handleSubmit() {
  const ok = await auth.login(username.value, password.value)
  if (ok) {
    chat.reset()
    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  }
}
</script>

<template>
  <div class="login-screen">
    <aside class="brand-panel">
      <div class="brand-content">
        <div class="brand-logo">国家能源集团</div>
        <h2 class="brand-title">智能办公助手</h2>
        <p class="brand-slogan">对话即办公，Agent 帮你搞定</p>
      </div>
      <div class="brand-accent-line" aria-hidden="true" />
    </aside>

    <section class="form-panel">
      <form class="login-card" @submit.prevent="handleSubmit">
        <h1>账号登录</h1>

        <div class="field">
          <label for="username">账号</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入账号"
            autocomplete="username"
          />
        </div>

        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>

        <p v-if="auth.error" class="error">{{ auth.error }}</p>

        <button type="submit" class="btn-login" :disabled="auth.loading">
          {{ auth.loading ? '登录中…' : '登录' }}
        </button>

        <p class="hint">预设账号：admin / admin123（管理员）· user_a / usera123 · user_b / userb123</p>
      </form>
    </section>
  </div>
</template>

<style scoped>
.login-screen {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: var(--surface);
}

.brand-panel {
  width: 45%;
  min-width: 320px;
  background: linear-gradient(180deg, #f6ab00 0%, #d84c14 100%);
  padding: 64px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: #fff;
}

.brand-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.brand-logo {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.brand-title {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.2;
}

.brand-slogan {
  font-size: 16px;
  opacity: 0.9;
  line-height: 1.5;
}

.brand-accent-line {
  height: 2px;
  width: 100%;
  background: linear-gradient(to right, #ffcf33 50%, #c11920);
  border-radius: 1px;
}

.form-panel {
  flex: 1;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.login-card {
  width: 400px;
  max-width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.login-card h1 {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field label {
  font-size: 13px;
  color: var(--text-secondary);
}

.field input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(193, 25, 32, 0.15);
}

.field input::placeholder {
  color: var(--text-muted);
}

.error {
  font-size: 13px;
  color: var(--primary);
}

.btn-login {
  height: 44px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-login:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-login:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.5;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .login-screen {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }

  .brand-panel {
    width: 100%;
    min-height: 240px;
    padding: 40px;
  }

  .form-panel {
    padding: 32px 24px;
  }
}
</style>
