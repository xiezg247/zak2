<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
    showWordmark?: boolean
  }>(),
  { size: 'md', showWordmark: true },
)
</script>

<template>
  <div class="brand-logo" :class="`size-${size}`">
    <img class="mark" src="/brand/logo-mark.svg" alt="" width="32" height="32" />
    <span v-if="showWordmark" class="word">zak2</span>
  </div>
</template>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--ink);
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1;
}
.mark {
  display: block;
  flex-shrink: 0;
  border-radius: 0.5rem;
}
.word {
  white-space: nowrap;
}
.size-sm .mark {
  width: 24px;
  height: 24px;
}
.size-sm .word {
  font-size: 1rem;
}
.size-md .mark {
  width: 32px;
  height: 32px;
}
.size-md .word {
  font-size: 1.125rem;
}
.size-lg .mark {
  width: 40px;
  height: 40px;
}
.size-lg .word {
  font-size: 1.75rem;
}
</style>
