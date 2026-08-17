<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from '../components/BrandLogo.vue'

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
    <div class="hero" aria-hidden="true">
      <div class="hero-inner">
        <BrandLogo size="lg" />
        <p class="hero-tag">量化终端 · 守则 · 自选 · 选股</p>
        <p class="hero-copy">浅色工作台，聚焦盘中决策与复盘节奏。</p>
      </div>
    </div>

    <div class="panel">
      <form class="card form" @submit.prevent="onSubmit">
        <div class="form-head">
          <BrandLogo class="mobile-brand" size="md" />
          <h1>欢迎回来</h1>
          <p class="sub">使用与桌面端相同的账号登录</p>
        </div>
        <label>
          用户名
          <input v-model="username" class="input-field" autocomplete="username" required />
        </label>
        <label>
          密码
          <input
            v-model="password"
            class="input-field"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '进入工作台' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  background: var(--surface-muted);
  padding: 0;
}

.hero {
  position: relative;
  display: grid;
  place-items: center;
  padding: 48px 40px;
  background:
    radial-gradient(ellipse 80% 60% at 20% 20%, rgba(230, 100, 50, 0.18), transparent 55%),
    radial-gradient(ellipse 70% 50% at 80% 80%, rgba(249, 212, 196, 0.55), transparent 50%),
    linear-gradient(160deg, #fff7f3 0%, var(--surface-muted) 55%, #f3f3f3 100%);
  border-right: 1px solid var(--line);
}

.hero-inner {
  max-width: 28rem;
  display: grid;
  gap: 14px;
}

.hero-tag {
  margin: 8px 0 0;
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--brand);
}

.hero-copy {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.55;
  color: var(--ink-muted);
}

.panel {
  display: grid;
  place-items: center;
  padding: 32px 24px;
}

.form {
  width: min(400px, 100%);
  padding: 32px 28px;
  display: grid;
  gap: 14px;
}

.form-head {
  display: grid;
  gap: 6px;
  margin-bottom: 4px;
}

.mobile-brand {
  display: none;
  margin-bottom: 8px;
}

.form-head h1 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.02em;
}

.sub {
  margin: 0;
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
  padding: 0.65rem 1rem;
}

@media (max-width: 900px) {
  .page {
    grid-template-columns: 1fr;
  }
  .hero {
    display: none;
  }
  .mobile-brand {
    display: inline-flex;
  }
}
</style>
