<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/screener'
    await router.replace(redirect)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <form class="card" @submit.prevent="onSubmit">
      <div class="brand">zak2</div>
      <p class="sub">使用与桌面端相同的账号登录</p>
      <label>
        用户名
        <input v-model="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="err">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
    </form>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: grid;
  place-items: center;
  background:
    radial-gradient(ellipse at top, #1b2a40 0%, transparent 55%),
    linear-gradient(160deg, #0c1016, #121820 60%, #0a0e14);
  padding: 24px;
}
.card {
  width: min(380px, 100%);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 28px 24px;
  display: grid;
  gap: 14px;
}
.brand {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.sub {
  margin: -6px 0 4px;
  color: var(--muted);
  font-size: 0.9rem;
}
label {
  display: grid;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
}
input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: 10px 12px;
}
button {
  margin-top: 6px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 14px;
  font-weight: 600;
}
button:disabled {
  opacity: 0.6;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
</style>
