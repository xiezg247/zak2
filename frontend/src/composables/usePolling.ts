import { onMounted, onUnmounted, watch, type WatchSource } from 'vue'

/**
 * 按 intervalMs() 周期调用 tick；deps 变化时重启定时器。
 * 用于行情兜底轮询等场景。
 */
export function usePolling(tick: () => void, intervalMs: () => number, deps: WatchSource[] = []) {
  let timer: number | undefined

  function stop() {
    if (timer != null) {
      window.clearInterval(timer)
      timer = undefined
    }
  }

  function restart() {
    stop()
    timer = window.setInterval(tick, intervalMs())
  }

  onMounted(restart)
  onUnmounted(stop)
  if (deps.length) {
    watch(deps, () => restart())
  }

  return { restart, stop }
}
