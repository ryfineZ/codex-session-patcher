import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../services/api'
import { useSettingsStore } from './settingsStore'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref([])
  const selectedId = ref(null)
  const preview = ref(null)
  const loading = ref(false)
  const previewLoading = ref(false)
  const aiRewrite = ref(null)
  const aiRewriteLoading = ref(false)
  const lastError = ref(null) // 最近一次错误信息，组件层可监听并展示
  const activeTab = ref('codex') // 'codex' | 'claude_code' | 'opencode'
  let _tabInitialized = false

  // 按格式拆分
  const codexSessions = computed(() => sessions.value.filter(s => s.format === 'codex'))
  const claudeSessions = computed(() => sessions.value.filter(s => s.format === 'claude_code'))
  const opencodeSessions = computed(() => sessions.value.filter(s => s.format === 'opencode'))

  // 当前 Tab 的会话
  const activeTabSessions = computed(() => {
    if (activeTab.value === 'codex') return codexSessions.value
    if (activeTab.value === 'opencode') return opencodeSessions.value
    return claudeSessions.value
  })

  async function fetchSessions(checkRefusal = true) {
    loading.value = true
    try {
      // 固定拉取全部格式，客户端按 format 字段拆分
      const data = await api.getSessions(!checkRefusal, 'auto')
      sessions.value = data.sessions

      // 仅首次加载时自动选 Tab，刷新时保留当前 Tab
      if (!_tabInitialized) {
        _tabInitialized = true
        // Codex 优先，有数据就停在 Codex
        if (codexSessions.value.length > 0) {
          activeTab.value = 'codex'
        } else {
          const settingsStore = useSettingsStore()
          if (settingsStore.claudeCodeEnabled && claudeSessions.value.length > 0) {
            activeTab.value = 'claude_code'
          } else if (opencodeSessions.value.length > 0) {
            activeTab.value = 'opencode'
          }
        }
      }

      // 自动选中当前 Tab 的第一条会话（仅初次无选中时）
      if (!selectedId.value && activeTabSessions.value.length > 0) {
        await selectSession(activeTabSessions.value[0].id)
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
      lastError.value = error.message || '加载会话列表失败'
    } finally {
      loading.value = false
    }
  }

  function setActiveTab(tab) {
    activeTab.value = tab
    // Tab 切换时重置预览，但不重新请求 API
    const stillExists = activeTabSessions.value.find(s => s.id === selectedId.value)
    if (!stillExists) {
      selectedId.value = null
      preview.value = null
      aiRewrite.value = null
    }
  }

  async function selectSession(id) {
    selectedId.value = id
    preview.value = null
    aiRewrite.value = null

    previewLoading.value = true
    try {
      const data = await api.previewSession(id)
      preview.value = data
    } catch (error) {
      console.error('Failed to preview session:', error)
      lastError.value = error.message || '预览会话失败'
    } finally {
      previewLoading.value = false
    }
  }

  async function previewSession(id) {
    previewLoading.value = true
    try {
      const data = await api.previewSession(id || selectedId.value)
      preview.value = data
      return data
    } catch (error) {
      console.error('Failed to preview session:', error)
      throw error
    } finally {
      previewLoading.value = false
    }
  }

  async function requestAIRewrite(id) {
    aiRewriteLoading.value = true
    aiRewrite.value = null
    try {
      const data = await api.aiRewriteSession(id || selectedId.value)
      if (data.success) {
        aiRewrite.value = data
        if (preview.value && preview.value.changes.length > 0 && data.items) {
          for (const item of data.items) {
            const change = preview.value.changes.find(c => c.line_num === item.line_num)
            if (change) {
              change.replacement = item.replacement
              change._ai_generated = true
            }
          }
        }
      }
      return data
    } catch (error) {
      console.error('AI rewrite failed:', error)
      throw error
    } finally {
      aiRewriteLoading.value = false
    }
  }

  async function patchSession(id) {
    let replacements = null
    if (aiRewrite.value?.items?.length > 0) {
      replacements = aiRewrite.value.items.map(item => ({
        line_num: item.line_num,
        replacement_text: item.replacement
      }))
    }
    try {
      const data = await api.patchSession(id || selectedId.value, replacements)
      if (data.success) {
        aiRewrite.value = null
        await fetchSessions()
        const currentSession = sessions.value.find(s => s.id === selectedId.value)
        if (currentSession) {
          await previewSession(selectedId.value)
        }
      }
      return data
    } catch (error) {
      console.error('Failed to patch session:', error)
      throw error
    }
  }

  async function listBackups(id) {
    return api.listBackups(id || selectedId.value)
  }

  async function restoreSession(id, backupFilename) {
    const data = await api.restoreSession(id || selectedId.value, backupFilename)
    if (data.success) {
      api.clearCache('sessions')
      await fetchSessions()
      if (selectedId.value) {
        await previewSession(selectedId.value)
      }
    }
    return data
  }

  function getSelectedSession() {
    return sessions.value.find(s => s.id === selectedId.value)
  }

  return {
    sessions,
    selectedId,
    preview,
    loading,
    previewLoading,
    aiRewrite,
    aiRewriteLoading,
    lastError,
    activeTab,
    codexSessions,
    claudeSessions,
    opencodeSessions,
    activeTabSessions,
    fetchSessions,
    setActiveTab,
    selectSession,
    previewSession,
    requestAIRewrite,
    patchSession,
    listBackups,
    restoreSession,
    getSelectedSession,
  }
})
