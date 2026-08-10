<script setup lang="ts">
import { computed } from 'vue'

export type CandleBar = {
  datetime: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const props = withDefaults(
  defineProps<{
    bars: CandleBar[]
    width?: number
    height?: number
  }>(),
  { width: 640, height: 280 },
)

const pad = { top: 12, right: 12, bottom: 28, left: 12 }
const volH = 56

type CandleGeom = {
  x: number
  yH: number
  yL: number
  bodyY: number
  bodyH: number
  bodyW: number
  volY: number
  volH: number
  color: string
}

const layout = computed(() => {
  const data = props.bars
  const w = props.width
  const h = props.height
  const chartH = h - volH - pad.top - pad.bottom
  const empty = { candles: [] as CandleGeom[], labels: [] as { x: number; text: string }[], midY: pad.top + chartH }
  if (data.length === 0) return empty

  const maxP = Math.max(...data.map((b) => b.high))
  const minP = Math.min(...data.map((b) => b.low))
  const span = maxP - minP || 1
  const maxV = Math.max(...data.map((b) => b.volume), 1)
  const slot = (w - pad.left - pad.right) / data.length
  const bodyW = Math.max(2, Math.min(10, slot * 0.65))
  const yPrice = (p: number) => pad.top + (1 - (p - minP) / span) * chartH
  const yVol = (v: number) => h - pad.bottom - (v / maxV) * (volH - 8)

  const candles: CandleGeom[] = data.map((b, i) => {
    const x = pad.left + slot * i + slot / 2
    const yO = yPrice(b.open)
    const yC = yPrice(b.close)
    const up = b.close >= b.open
    return {
      x,
      yH: yPrice(b.high),
      yL: yPrice(b.low),
      bodyY: Math.min(yO, yC),
      bodyH: Math.max(1.5, Math.abs(yC - yO)),
      bodyW,
      volY: yVol(b.volume),
      volH: Math.max(1, h - pad.bottom - yVol(b.volume)),
      color: up ? '#d4544a' : '#3fae6c',
    }
  })

  const labels: { x: number; text: string }[] = []
  const step = Math.max(1, Math.floor(data.length / 4))
  for (let i = 0; i < data.length; i += step) {
    labels.push({
      x: pad.left + slot * i + slot / 2,
      text: data[i].datetime.slice(5, 10),
    })
  }
  return { candles, labels, midY: pad.top + chartH }
})

const last = computed(() => (props.bars.length ? props.bars[props.bars.length - 1] : null))
</script>

<template>
  <div class="candle">
    <svg :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" role="img">
      <line
        :x1="pad.left"
        :x2="width - pad.right"
        :y1="layout.midY"
        :y2="layout.midY"
        stroke="currentColor"
        stroke-opacity="0.15"
      />
      <template v-for="(c, i) in layout.candles" :key="i">
        <line :x1="c.x" :y1="c.yH" :x2="c.x" :y2="c.yL" :stroke="c.color" stroke-width="1" />
        <rect :x="c.x - c.bodyW / 2" :y="c.bodyY" :width="c.bodyW" :height="c.bodyH" :fill="c.color" />
        <rect
          :x="c.x - c.bodyW / 2"
          :y="c.volY"
          :width="c.bodyW"
          :height="c.volH"
          :fill="c.color"
          opacity="0.4"
        />
      </template>
      <text
        v-for="(lb, i) in layout.labels"
        :key="'l' + i"
        :x="lb.x"
        :y="height - 8"
        text-anchor="middle"
        class="axis"
      >
        {{ lb.text }}
      </text>
    </svg>
    <div v-if="last" class="hint">
      <span>{{ last.datetime.slice(0, 10) }}</span>
      <span>O {{ last.open.toFixed(2) }}</span>
      <span>H {{ last.high.toFixed(2) }}</span>
      <span>L {{ last.low.toFixed(2) }}</span>
      <span>C {{ last.close.toFixed(2) }}</span>
    </div>
  </div>
</template>

<style scoped>
.candle {
  color: var(--muted);
  width: 100%;
}
.candle svg {
  width: 100%;
  height: 240px;
  display: block;
}
.axis {
  fill: var(--muted);
  font-size: 10px;
}
.hint {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--muted);
  font-family: var(--mono);
}
</style>
