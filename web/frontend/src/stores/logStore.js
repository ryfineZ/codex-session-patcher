import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLogStore = defineStore('log', () => {
  const logs = ref([])
  const collapsed = ref(true)

  function addLog(message, type = 'info') {
    const id = Date.now().toString(36) + Math.random().toString(36).substr(2)
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    logs.value.push({ id, timestamp, type, message })

    // 保持最多 100 条日志
    if (logs.value.length > 100) {
      logs.value.shift()
    }
  }

  function clearLogs() {
    logs.value = []
  }

  function toggle() {
    collapsed.value = !collapsed.value
  }

  return {
    logs,
    collapsed,
    addLog,
    clearLogs,
    toggle
  }
})
