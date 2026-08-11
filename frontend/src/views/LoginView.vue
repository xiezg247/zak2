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
    <form class="card form" @submit.prevent="onSubmit">
      <div class="brand">
        <span class="logo-mark" aria-hidden="true" />
        zak2
      </div>
      <p class="sub">使用与桌面端相同的账号登录</p>
      <label>
        用户名
        <input class="input-field" v-model="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input
          class="input-field"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <p v-if="error" class="err">{{ error }}</p>
      <button class="btn-primary" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: grid;
  place-items: center;
  background: var(--surface-muted);
  padding: 24px;
}
.form {
  width: min(380px, 100%);
  padding: 28px 24px;
  display: grid;
  gap: 14px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink);
}
.logo-mark {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: var(--brand);
}
.sub {
  margin: -6px 0 4px;
  color: var(--ink-muted);
  font-size: 0.9rem;
}
label {
  display: grid;
  gap: 6px;
  color: var(--ink);
  font-size: 0.875rem;
  font-weight: 500;
}
.err {
  margin: 0;
  border-radius: 0.5rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.btn-primary {
  width: 100%;
  margin-top: 4px;
}
</style>
