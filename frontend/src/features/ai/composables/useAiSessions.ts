import { ref } from 'vue'
import { aiApi, type Session } from '../../../api/ai'

export function useAiSessions() {
  const sessions = ref<Session[]>([])
  const sessionsPage = ref(1)
  const sessionsPages = ref(0)
  const sessionsTotal = ref(0)
  const sessionId = ref('')

  async function refreshSessions() {
    const p = await aiApi.sessionsPage(sessionsPage.value, 20)
    sessions.value = p.items
    sessionsTotal.value = p.total
    sessionsPages.value = p.pages
    if (!sessionId.value && sessions.value.length) {
      sessionId.value = sessions.value[0].id
    }
  }

  async function goSessionsPage(p: number) {
    sessionsPage.value = p
    await refreshSessions()
  }

  async function newSession() {
    const s = await aiApi.createSession()
    sessions.value = [s, ...sessions.value]
    sessionId.value = s.id
    return s
  }

  async function removeSession(id: string) {
    await aiApi.deleteSession(id)
    const cleared = sessionId.value === id
    if (cleared) sessionId.value = ''
    await refreshSessions()
    return cleared
  }

  function selectSession(id: string) {
    sessionId.value = id
  }

  return {
    sessions,
    sessionsPage,
    sessionsPages,
    sessionsTotal,
    sessionId,
    refreshSessions,
    goSessionsPage,
    newSession,
    removeSession,
    selectSession,
  }
}
