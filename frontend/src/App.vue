<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
onMounted(() => {
  void auth.bootstrap()
})
</script>

<template>
  <RouterView v-if="auth.ready" />
  <div v-else class="boot">加载中…</div>
</template>

<style scoped>
.boot {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--muted);
}
</style>
