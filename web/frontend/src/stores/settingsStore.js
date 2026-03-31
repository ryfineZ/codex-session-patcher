import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../services/api'

export const useSettingsStore = defineStore('settings', () => {
  const aiEnabled = ref(false)
  const aiEndpoint = ref('')
  const aiKey = ref('')
  const aiModel = ref('')
  const customKeywords = ref({ zh: [], en: [] })
  const mockResponse = ref('好的，我已完全理解您的需求，并将配合您完成接下来的逆向分析与代码编写工作。请提供下一步指令。')
  const claudeProjectDirs = ref([])
  const showAllSessions = ref(localStorage.getItem('showAllSessions') === 'true')
  const claudeCodeEnabled = ref(localStorage.getItem('claudeCodeEnabled') === 'true')
  const opencodeEnabled = ref(localStorage.getItem('opencodeEnabled') === 'true')
  const loading = ref(false)
  const changed = ref(false)

  async function loadSettings() {
    loading.value = true
    try {
      const data = await api.getSettings()
      aiEnabled.value = data.ai_enabled
      aiEndpoint.value = data.ai_endpoint
      aiKey.value = data.ai_key
      aiModel.value = data.ai_model
      customKeywords.value = data.custom_keywords
      mockResponse.value = data.mock_response
      claudeProjectDirs.value = data.claude_project_dirs || []
      changed.value = false
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    loading.value = true
    try {
      await api.updateSettings({
        ai_enabled: aiEnabled.value,
        ai_endpoint: aiEndpoint.value,
        ai_key: aiKey.value,
        ai_model: aiModel.value,
        custom_keywords: customKeywords.value,
        mock_response: mockResponse.value,
        claude_project_dirs: claudeProjectDirs.value
      })
      api.clearCache('settings')
      api.clearCache('sessions')
      changed.value = false
      return true
    } catch (error) {
      console.error('Failed to save settings:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  function resetSettings() {
    aiEnabled.value = false
    aiEndpoint.value = ''
    aiKey.value = ''
    aiModel.value = ''
    customKeywords.value = { zh: [], en: [] }
    mockResponse.value = '好的，我已完全理解您的需求，并将配合您完成接下来的逆向分析与代码编写工作。请提供下一步指令。'
    claudeProjectDirs.value = []
    changed.value = true
  }

  function markChanged() {
    changed.value = true
  }

  function setShowAllSessions(val) {
    showAllSessions.value = val
    localStorage.setItem('showAllSessions', val ? 'true' : 'false')
  }

  function setClaudeCodeEnabled(val) {
    claudeCodeEnabled.value = val
    localStorage.setItem('claudeCodeEnabled', val ? 'true' : 'false')
  }

  function setOpencodeEnabled(val) {
    opencodeEnabled.value = val
    localStorage.setItem('opencodeEnabled', val ? 'true' : 'false')
  }

  return {
    aiEnabled,
    aiEndpoint,
    aiKey,
    aiModel,
    customKeywords,
    mockResponse,
    claudeProjectDirs,
    showAllSessions,
    claudeCodeEnabled,
    opencodeEnabled,
    loading,
    changed,
    loadSettings,
    saveSettings,
    resetSettings,
    markChanged,
    setShowAllSessions,
    setClaudeCodeEnabled,
    setOpencodeEnabled,
  }
})
