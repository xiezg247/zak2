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
const showPassword = ref(false)

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
      <div class="hero-glow" aria-hidden="true"></div>
      <div class="hero-inner">
        <span class="hero-badge">量化工作台</span>
        <BrandLogo size="lg" />
        <p class="hero-tag">守则 · 自选 · 选股 · 复盘</p>
        <p class="hero-copy">浅色工作台，聚焦盘中决策与复盘节奏。</p>
        <ul class="hero-features">
          <li>盘中决策</li>
          <li>复盘节奏</li>
          <li>自选监控</li>
        </ul>
      </div>
    </div>

    <div class="panel">
      <form class="card form" @submit.prevent="onSubmit">
        <div class="form-head">
          <BrandLogo class="mobile-brand" size="md" />
          <h1>欢迎回来</h1>
          <p class="sub">使用与桌面端相同的账号登录</p>
        </div>

        <label class="field">
          <span class="field-label">用户名</span>
          <input
            v-model="username"
            class="input-field"
            type="text"
            autocomplete="username"
            placeholder="请输入用户名"
            required
            autofocus
          />
        </label>

        <label class="field">
          <span class="field-label">密码</span>
          <div class="password-wrap">
            <input
              v-model="password"
              class="input-field"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="请输入密码"
              required
            />
            <button
              type="button"
              class="password-toggle"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <svg
                v-if="!showPassword"
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg
                v-else
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M3 3l18 18" />
                <path d="M10.5 5.2A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.6 3.4" />
                <path d="M6.6 6.6A16.7 16.7 0 0 0 2 12s3.5 7 10 7a10.7 10.7 0 0 0 4.4-.9" />
                <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
              </svg>
            </button>
          </div>
        </label>

        <transition name="err">
          <p v-if="error" class="err" role="alert">
            <svg
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
            {{ error }}
          </p>
        </transition>

        <button class="btn-primary submit" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
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
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  background: var(--surface-muted);
  padding: 0;
}

/* ---------- Hero ---------- */
.hero {
  position: relative;
  display: grid;
  place-items: center;
  padding: 48px 40px;
  overflow: hidden;
  background:
    radial-gradient(ellipse 80% 60% at 18% 18%, rgba(230, 100, 50, 0.16), transparent 55%),
    radial-gradient(ellipse 70% 55% at 82% 82%, rgba(249, 212, 196, 0.6), transparent 52%),
    linear-gradient(160deg, #fff7f3 0%, var(--surface-muted) 55%, #f3f3f3 100%);
  border-right: 1px solid var(--line);
  isolation: isolate;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(rgba(230, 100, 50, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(230, 100, 50, 0.05) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse 90% 80% at 50% 50%, #000 40%, transparent 100%);
}

.hero-glow {
  position: absolute;
  top: 18%;
  right: 12%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(230, 100, 50, 0.18), transparent 70%);
  filter: blur(10px);
  z-index: -1;
}

.hero-inner {
  max-width: 28rem;
  display: grid;
  gap: 14px;
  animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.hero-badge {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--brand-soft);
  background: rgba(255, 255, 255, 0.6);
  color: var(--brand-dark);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.hero-tag {
  margin: 8px 0 0;
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--brand);
}

.hero-copy {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.55;
  color: var(--ink-muted);
}

.hero-features {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-features li {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0.4rem 0.8rem;
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--line-soft);
  color: var(--ink);
  font-size: 0.82rem;
  font-weight: 500;
  box-shadow: var(--shadow-card);
}

.hero-features li::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand);
}

/* ---------- Panel / Form ---------- */
.panel {
  display: grid;
  place-items: center;
  padding: 32px 24px;
}

.form {
  width: min(400px, 100%);
  padding: 34px 30px;
  display: grid;
  gap: 16px;
  box-shadow: var(--shadow-panel);
  animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.12s both;
}

.form-head {
  display: grid;
  gap: 6px;
  margin-bottom: 6px;
}

.mobile-brand {
  display: none;
  margin-bottom: 8px;
}

.form-head h1 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.02em;
}

.sub {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.9rem;
}

.field {
  display: grid;
  gap: 7px;
}

.field-label {
  color: var(--ink);
  font-size: 0.875rem;
  font-weight: 500;
}

.field .input-field {
  padding: 0.65rem 0.85rem;
  font-size: 0.925rem;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.field .input-field:focus {
  background: #fffdfb;
}

.password-wrap {
  position: relative;
}

.password-wrap .input-field {
  padding-right: 2.6rem;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 0.5rem;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 0.4rem;
  background: transparent;
  color: var(--ink-faint);
  transition: color 0.15s ease;
}

.password-toggle:hover {
  color: var(--brand);
}

/* ---------- Error ---------- */
.err {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  border-radius: 0.5rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  padding: 0.55rem 0.8rem;
  font-size: 0.875rem;
  border: 1px solid var(--brand-soft);
}

.err svg {
  flex-shrink: 0;
}

/* ---------- Submit ---------- */
.submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  margin-top: 4px;
  padding: 0.7rem 1rem;
  font-size: 0.925rem;
  transition:
    background 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(230, 100, 50, 0.28);
}

.submit:active:not(:disabled) {
  transform: translateY(0);
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* ---------- Animations ---------- */
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.err-enter-active,
.err-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.err-enter-from,
.err-leave-to {
  opacity: 0;
  transform: translateY(-4px);
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
