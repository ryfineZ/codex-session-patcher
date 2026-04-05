<template>
  <n-config-provider :theme="darkTheme" :locale="naiveLocale" :date-locale="naiveDateLocale">
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
            <img src="/logo.svg" alt="logo" class="app-logo" />
            <span class="title">Codex Session Patcher</span>
          </div>
          <div class="header-right">
            <!-- GitHub -->
            <n-tooltip trigger="hover" placement="bottom">
              <template #trigger>
                <a href="https://github.com/ryfineZ/codex-session-patcher" target="_blank" class="social-link" aria-label="GitHub">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
                </a>
              </template>
              GitHub
            </n-tooltip>

            <!-- X (Twitter) -->
            <n-tooltip trigger="hover" placement="bottom">
              <template #trigger>
                <a href="https://x.com/ZhangYufan73644" target="_blank" class="social-link" aria-label="X">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                </a>
              </template>
              X (Twitter)
            </n-tooltip>

            <!-- 微信公众号 -->
            <n-popover trigger="click" placement="bottom-end" :width="200">
              <template #trigger>
                <button class="social-link" aria-label="微信公众号">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.161 1.71-1.484 1.255-2.263 3.057-1.944 4.85.976 5.58 9.277 7.679 14.6 4.066.061-.04.135-.06.211-.06a.29.29 0 0 1 .089.014l1.523.868a.29.29 0 0 0 .14.047c.134 0 .24-.11.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1 .181-.555C23.002 17.394 24 15.829 24 14.098c0-3.226-3.13-5.765-7.062-5.24zm-3.85 3.045c.56 0 1.012.46 1.012 1.028a1.02 1.02 0 0 1-1.012 1.028 1.02 1.02 0 0 1-1.013-1.028c0-.568.453-1.028 1.013-1.028zm5.886 0c.56 0 1.012.46 1.012 1.028a1.02 1.02 0 0 1-1.012 1.028 1.02 1.02 0 0 1-1.013-1.028c0-.568.453-1.028 1.013-1.028z"/></svg>
                </button>
              </template>
              <div style="text-align: center; padding: 8px 0">
                <img src="/qr-wechat-mp.png" alt="微信公众号" style="width: 160px; height: 160px; border-radius: 4px" />
                <div style="margin-top: 8px; font-size: 12px; opacity: 0.7">钢之AI术师</div>
              </div>
            </n-popover>

            <!-- Buy me a coffee -->
            <n-button size="small" type="primary" class="sponsor-btn" @click="showSponsor = true">
              ☕ Buy me a coffee
            </n-button>

            <LocaleSwitch />
          </div>

          <!-- 赞助弹窗 -->
          <n-modal v-model:show="showSponsor" preset="card" :style="{ width: '320px' }" title="Buy me a coffee ☕">
            <n-tabs type="segment" size="small" v-model:value="sponsorTab">
              <n-tab-pane name="wechat" tab="微信赞赏">
                <div style="text-align: center; padding: 12px 0">
                  <img src="/qr-sponsor-wechat.png" alt="微信收款码" style="width: 200px; height: 200px; border-radius: 8px" />
                  <div style="margin-top: 12px; font-size: 13px; opacity: 0.7">感谢支持！🙏</div>
                </div>
              </n-tab-pane>
              <n-tab-pane name="crypto" tab="USDC (Arbitrum)">
                <div style="text-align: center; padding: 12px 0">
                  <img src="/qr-sponsor-crypto.png" alt="USDC 收款码" style="width: 200px; height: 200px; border-radius: 8px" />
                  <div style="margin-top: 12px">
                    <n-text style="font-size: 11px; font-family: monospace; word-break: break-all; opacity: 0.8">
                      0xAeEBb76262D5D452Aa0D4b19E193Dd2402397d02
                    </n-text>
                  </div>
                  <n-button size="small" style="margin-top: 8px" @click="copyWalletAddr">复制地址</n-button>
                </div>
              </n-tab-pane>
            </n-tabs>
          </n-modal>
        </n-layout-header>

        <!-- Tab 导航 -->
        <n-tabs v-model:value="activeTab" type="line" class="main-tabs" @update:value="handleTabChange">
          <n-tab name="enhance">
            <template #icon>
              <n-icon><SparklesOutline /></n-icon>
            </template>
            {{ $t('nav.enhance') }}
          </n-tab>
          <n-tab name="sessions">
            <template #icon>
              <n-icon><ListOutline /></n-icon>
            </template>
            {{ $t('nav.sessions') }}
          </n-tab>
          <n-tab name="settings">
            <template #icon>
              <n-icon><SettingsOutline /></n-icon>
            </template>
            {{ $t('nav.settings') }}
          </n-tab>
          <n-tab name="help">
            <template #icon>
              <n-icon><HelpCircleOutline /></n-icon>
            </template>
            {{ $t('nav.help') }}
          </n-tab>
        </n-tabs>

        <!-- 主内容区 -->
        <n-layout has-sider class="app-content" v-show="activeTab === 'sessions'">
          <!-- 左侧会话列表 -->
          <n-layout-sider
            bordered
            :width="340"
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
            <PreviewPanel ref="previewPanelRef" v-model:cleanReasoning="cleanReasoning" />
            <ActionBar :preview-panel-ref="previewPanelRef" :clean-reasoning="cleanReasoning" />
          </n-layout-content>
        </n-layout>

        <!-- 其他 Tab 内容 -->
        <n-layout-content v-show="activeTab !== 'sessions'" class="tab-content">
          <PromptEnhancePanel v-if="activeTab === 'enhance'" />
          <SettingsPanel v-if="activeTab === 'settings'" />
          <HelpPanel v-if="activeTab === 'help'" />
        </n-layout-content>

        <!-- 底部日志面板 -->
        <LogPanel />
      </n-layout>
    </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { darkTheme, zhCN, dateZhCN, enUS, dateEnUS, NDialogProvider } from 'naive-ui'
import { SettingsOutline, MenuOutline, ListOutline, SparklesOutline, HelpCircleOutline } from '@vicons/ionicons5'
import SessionList from './components/SessionList.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import ActionBar from './components/ActionBar.vue'
import LogPanel from './components/LogPanel.vue'
import PromptEnhancePanel from './components/PromptEnhancePanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import HelpPanel from './components/HelpPanel.vue'
import LocaleSwitch from './components/LocaleSwitch.vue'
import { useSessionStore } from './stores/sessionStore'
import { useSettingsStore } from './stores/settingsStore'
import { useLogStore } from './stores/logStore'
import { useLocaleStore } from './stores/localeStore'

const { t } = useI18n()
const activeTab = ref('enhance')
const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const showSponsor = ref(false)
const sponsorTab = ref('wechat')
const previewPanelRef = ref(null)
const cleanReasoning = ref(true)  // 是否清理推理内容

async function copyWalletAddr() {
  try {
    await navigator.clipboard.writeText('0xAeEBb76262D5D452Aa0D4b19E193Dd2402397d02')
  } catch {}
}
const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const logStore = useLogStore()
const localeStore = useLocaleStore()

// Naive UI locale
const naiveLocale = computed(() => {
  return localeStore.currentLocale === 'en-US' ? enUS : zhCN
})

const naiveDateLocale = computed(() => {
  return localeStore.currentLocale === 'en-US' ? dateEnUS : dateZhCN
})

// 初始化：加载会话列表
sessionStore.fetchSessions()

// Tab 切换时加载设置
function handleTabChange(tab) {
  if (tab === 'settings') {
    settingsStore.loadSettings()
  }
}

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

.app-logo {
  width: 28px;
  height: 28px;
  display: block;
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.social-link {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--n-text-color-3, #888);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-decoration: none;
  transition: color 0.2s, background 0.2s;
}
.social-link:hover {
  color: var(--n-text-color-1, #fff);
  background: rgba(255,255,255,0.08);
}

.sponsor-btn {
  font-size: 12px;
}

@media (max-width: 600px) {
  .sponsor-btn {
    display: none;
  }
}

.menu-toggle {
  display: none;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.main-tabs {
  padding: 0 16px;
  background: var(--color-bg-1);
  border-bottom: 1px solid var(--color-border);
}

.main-tabs :deep(.n-tabs-nav) {
  padding: 0;
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

.tab-content {
  flex: 1;
  padding: 16px;
  padding-bottom: 56px;
  background: var(--color-bg-2);
  overflow: auto;
}

/* 响应式布局 */
@media (max-width: 1024px) {
  .menu-toggle {
    display: flex;
  }

  .session-sider {
    position: fixed;
    top: calc(var(--header-height) + 40px);
    left: 0;
    bottom: 0;
    z-index: 100;
    background: var(--color-bg-1);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    top: calc(var(--header-height) + 40px);
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }
}

@media (max-width: 768px) {
  .main-content, .tab-content {
    padding: 12px;
  }
}
</style>
