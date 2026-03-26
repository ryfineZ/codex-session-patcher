<template>
  <n-config-provider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-dialog-provider>
        <n-layout class="app-layout">
        <!-- 顶部 Header -->
        <n-layout-header bordered class="app-header">
          <div class="header-left">
            <n-button
              quaternary
              class="menu-toggle hide-tablet"
              @click="sidebarCollapsed = !sidebarCollapsed"
            >
              <template #icon>
                <n-icon><MenuOutline /></n-icon>
              </template>
            </n-button>
            <n-icon size="24" color="var(--color-primary)">
              <CodeSlash />
            </n-icon>
            <span class="title">Codex Session Patcher</span>
          </div>
          <div class="header-right">
            <n-button quaternary @click="showSettings = true">
              <template #icon>
                <n-icon><SettingsOutline /></n-icon>
              </template>
              设置
            </n-button>
          </div>
        </n-layout-header>

        <!-- 主内容区 -->
        <n-layout has-sider class="app-content">
          <!-- 左侧会话列表 -->
          <n-layout-sider
            bordered
            :width="280"
            :collapsed-width="0"
            :collapsed="sidebarCollapsed"
            :native-scrollbar="false"
            class="session-sider"
            collapse-mode="transform"
            @collapse="sidebarCollapsed = true"
            @expand="sidebarCollapsed = false"
          >
            <SessionList />
          </n-layout-sider>

          <!-- 移动端遮罩 -->
          <div
            v-if="!sidebarCollapsed && isMobile"
            class="sidebar-overlay"
            @click="sidebarCollapsed = true"
          />

          <!-- 右侧内容区 -->
          <n-layout-content class="main-content">
            <PreviewPanel />
            <ActionBar />
          </n-layout-content>
        </n-layout>

        <!-- 底部日志面板 -->
        <LogPanel />

        <!-- 设置抽屉 -->
        <SettingsDrawer v-model:show="showSettings" />
      </n-layout>
    </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { darkTheme, zhCN, dateZhCN, NDialogProvider } from 'naive-ui'
import { CodeSlash, SettingsOutline, MenuOutline } from '@vicons/ionicons5'
import SessionList from './components/SessionList.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import ActionBar from './components/ActionBar.vue'
import LogPanel from './components/LogPanel.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'
import { useSessionStore } from './stores/sessionStore'
import { useSettingsStore } from './stores/settingsStore'
import { useLogStore } from './stores/logStore'

const showSettings = ref(false)
const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const logStore = useLogStore()

// 初始化：加载会话列表
sessionStore.fetchSessions()

// 打开设置时加载配置
watch(showSettings, (val) => {
  if (val) {
    settingsStore.loadSettings()
  }
})

// 响应式检测
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) {
    sidebarCollapsed.value = true
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// WebSocket 连接管理
let ws = null
let reconnectTimer = null
const wsConnected = ref(false)

const connectWebSocket = () => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
    console.log('WebSocket connected')
  }

  ws.onclose = () => {
    wsConnected.value = false
    console.log('WebSocket disconnected, reconnecting...')
    // 3秒后重连
    reconnectTimer = setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'log') {
        const { level, message } = data.data
        logStore.addLog(message, level)
      }
    } catch (e) {
      console.error('WebSocket message parse error:', e)
    }
  }
}

connectWebSocket()

// 组件卸载时清理 WebSocket
onUnmounted(() => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
  }
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: var(--header-height);
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-bg-1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-toggle {
  display: none;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-content {
  flex: 1;
  min-height: 0;
}

.session-sider {
  background: var(--color-bg-1);
}

.sidebar-overlay {
  display: none;
}

.main-content {
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-bottom: 56px; /* 日志面板收起时的高度 + 安全边距 */
  background: var(--color-bg-2);
}

/* 响应式布局 */
@media (max-width: 1024px) {
  .menu-toggle {
    display: flex;
  }

  .session-sider {
    position: fixed;
    top: var(--header-height);
    left: 0;
    bottom: 0;
    z-index: 100;
    background: var(--color-bg-1);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    top: var(--header-height);
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }
}

@media (max-width: 768px) {
  .main-content {
    padding: 12px;
  }

  .header-right .n-button__content span:last-child {
    display: none;
  }
}
</style>
