<script setup lang="ts">
import type { StrategyProfile } from '../../../api/backtest'

defineProps<{
  profiles: StrategyProfile[]
  activeProfileId: string
}>()

const emit = defineEmits<{
  apply: [profile: StrategyProfile]
}>()
</script>

<template>
  <section v-if="profiles.length" class="profiles">
    <button
      v-for="p in profiles"
      :key="p.profile_id"
      type="button"
      class="chip"
      :class="{ on: activeProfileId === p.profile_id }"
      :title="p.description"
      @click="emit('apply', p)"
    >
      {{ p.name }}
    </button>
  </section>
</template>

<style scoped>
.profiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
  color: var(--muted);
  cursor: pointer;
}
.chip.on {
  border-color: var(--accent);
  color: var(--text);
  font-weight: 500;
}
</style>
