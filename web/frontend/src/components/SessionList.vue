<template>
  <div class="session-list">
    <div class="list-header">
      <span class="title">{{ $t('session.title') }}</span>
      <div class="header-actions">
        <n-button text size="small" @click="refresh" :loading="loading">
          <template #icon>
            <n-icon><RefreshOutline /></n-icon>
          </template>
        </n-button>
      </div>
    </div>

    <!-- 格式 Tab（多格式时显示） -->
    <div v-if="settingsStore.claudeCodeEnabled || settingsStore.opencodeEnabled" class="format-tabs">
      <button
        class="format-tab"
        :class="{ active: sessionStore.activeTab === 'codex' }"
        @click="sessionStore.setActiveTab('codex')"
      >
        {{ $t('session.format_codex') }}
        <span class="tab-count">{{ sessionStore.codexSessions.length }}</span>
      </button>
      <button
        v-if="settingsStore.claudeCodeEnabled"
        class="format-tab"
        :class="{ active: sessionStore.activeTab === 'claude_code' }"
        @click="sessionStore.setActiveTab('claude_code')"
      >
        {{ $t('session.format_claude') }}
        <span class="tab-count">{{ sessionStore.claudeSessions.length }}</span>
      </button>
      <button
        v-if="settingsStore.opencodeEnabled"
        class="format-tab"
        :class="{ active: sessionStore.activeTab === 'opencode' }"
        @click="sessionStore.setActiveTab('opencode')"
      >
        {{ $t('session.format_opencode') }}
        <span class="tab-count">{{ sessionStore.opencodeSessions.length }}</span>
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <n-input
        v-model:value="searchQuery"
        :placeholder="$t('session.search')"
        clearable
        size="small"
      >
        <template #prefix>
          <n-icon><SearchOutline /></n-icon>
        </template>
      </n-input>
    </div>

    <!-- 过滤标签 -->
    <div class="filter-tabs">
      <n-button
        v-if="settingsStore.showAllSessions"
        size="tiny"
        :type="filterMode === 'all' ? 'primary' : 'default'"
        :secondary="filterMode === 'all'"
        @click="filterMode = 'all'"
      >
        {{ $t('session.all') }} {{ visibleSessions.length }}
      </n-button>
      <n-button
        size="tiny"
        :type="filterMode === 'refusal' ? 'error' : 'default'"
        :secondary="filterMode === 'refusal'"
        @click="filterMode = 'refusal'"
      >
        {{ $t('session.hasRefusal') }} {{ refusalCount }}
      </n-button>
      <n-button
        v-if="settingsStore.showAllSessions"
        size="tiny"
        :type="filterMode === 'clean' ? 'success' : 'default'"
        :secondary="filterMode === 'clean'"
        @click="filterMode = 'clean'"
      >
        {{ $t('session.noRefusal') }} {{ visibleSessions.length - refusalCount }}
      </n-button>
      <n-button
        size="tiny"
        :type="filterMode === 'patched' ? 'info' : 'default'"
        :secondary="filterMode === 'patched'"
        @click="filterMode = 'patched'"
      >
        {{ $t('session.cleaned') }} {{ patchedCount }}
      </n-button>
    </div>

    <div class="list-scrollbar">
      <div v-if="loading" class="loading-state">
        <n-spin size="medium" />
      </div>
      <div v-else class="list-content">
        <n-empty v-if="filteredSessions.length === 0 && visibleSessions.length === 0" :description="$t('session.empty')" />
        <!-- 当前过滤模式下无结果，但实际有会话时给出提示 -->
        <div v-if="filteredSessions.length === 0 && visibleSessions.length > 0" class="filter-hint">
          <n-text depth="3" style="font-size: 12px">{{ visibleSessions.length }} 条会话被过滤隐藏</n-text>
          <n-button text size="tiny" type="primary" @click="filterMode = 'all'" style="font-size: 12px">
            显示全部
          </n-button>
        </div>

        <!-- 按日期分组显示 -->
        <div v-for="group in groupedSessions" :key="group.label" class="date-group">
          <div class="date-label" @click="toggleGroup(group.label)">
            <n-icon class="group-icon" :class="{ expanded: expandedGroups.has(group.label) }">
              <ChevronDownOutline />
            </n-icon>
            <span>{{ group.label }}</span>
            <span class="count">{{ group.sessions.length }}</span>
          </div>

          <div v-show="expandedGroups.has(group.label)" class="group-sessions">
            <div
              v-for="session in group.sessions"
              :key="session.id"
              class="session-item"
              :class="{ selected: session.id === sessionStore.selectedId, 'has-refusal': session.has_refusal }"
            >
              <div class="session-main" @click="selectSession(session.id)">
                <div class="session-info">
                  <span class="session-id">{{ session.id }}</span>
                  <span class="session-time">{{ formatTime(session.mtime) }}</span>
                </div>
                <div class="session-meta">
                  <n-tag
                    v-if="session.has_refusal"
                    type="error"
                    size="small"
                  >
                    {{ session.refusal_count }}
                  </n-tag>
                  <n-tag v-else type="success" size="small">
                    OK
                  </n-tag>
                  <n-tag
                    v-if="session.has_backup"
                    type="info"
                    size="small"
                  >
                    {{ $t('session.cleaned') }}
                  </n-tag>
                  <n-icon
                    class="expand-icon"
                    :class="{ expanded: expandedIds.has(session.id) }"
                    @click.stop="toggleExpand(session.id)"
                  >
                    <ChevronDownOutline />
                  </n-icon>
                </div>
              </div>

              <div v-show="expandedIds.has(session.id)" class="session-detail">
                <div v-if="session.project_path" class="detail-item">
                  <span class="label">{{ $t('session.project') }}:</span>
                  <span class="value" :title="session.project_path">{{ truncate(session.project_path, 30) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">{{ $t('session.size') }}:</span>
                  <span class="value">{{ formatSize(session.size) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">{{ $t('session.modified') }}:</span>
                  <span class="value">{{ session.mtime }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { RefreshOutline, ChevronDownOutline, SearchOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'
import { useSettingsStore } from '../stores/settingsStore'

const { t } = useI18n()
const message = useMessage()
const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()

// 监听 store 错误并通知用户
watch(() => sessionStore.lastError, (err) => {
  if (err) {
    message.error(err)
    sessionStore.lastError = null
  }
})
const expandedIds = reactive(new Set())
const expandedGroups = reactive(new Set([t('session.today'), t('session.yesterday')]))

const searchQuery = ref('')
const filterMode = ref('refusal')  // 'all' | 'refusal' | 'clean' | 'patched'
const loading = ref(false)

// 关闭"显示全部"时，如果当前在 all/clean 过滤，自动切回 refusal
watch(() => settingsStore.showAllSessions, (val) => {
  if (!val && (filterMode.value === 'all' || filterMode.value === 'clean')) {
    filterMode.value = 'refusal'
  }
})

// 关闭 Claude Code 支持时，强制切回 Codex
watch(() => settingsStore.claudeCodeEnabled, (val) => {
  if (!val && sessionStore.activeTab === 'claude_code') {
    sessionStore.setActiveTab('codex')
  }
})

// 关闭 OpenCode 支持时，强制切回 Codex
watch(() => settingsStore.opencodeEnabled, (val) => {
  if (!val && sessionStore.activeTab === 'opencode') {
    sessionStore.setActiveTab('codex')
  }
})

// 当前可见的会话列表（受格式开关影响）
const visibleSessions = computed(() => {
  if (!settingsStore.claudeCodeEnabled && sessionStore.activeTab === 'claude_code') {
    return sessionStore.codexSessions
  }
  return sessionStore.activeTabSessions
})

const refusalCount = computed(() => {
  return visibleSessions.value.filter(s => s.has_refusal).length
})

const patchedCount = computed(() => {
  return visibleSessions.value.filter(s => s.has_backup).length
})

// 过滤后的会话列表
const filteredSessions = computed(() => {
  let list = visibleSessions.value
  // 按拒绝状态过滤
  if (filterMode.value === 'refusal') {
    list = list.filter(s => s.has_refusal)
  } else if (filterMode.value === 'clean') {
    list = list.filter(s => !s.has_refusal)
  } else if (filterMode.value === 'patched') {
    list = list.filter(s => s.has_backup)
  }
  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    list = list.filter(s =>
      s.id.toLowerCase().includes(query) ||
      s.filename.toLowerCase().includes(query) ||
      (s.project_path || '').toLowerCase().includes(query)
    )
  }
  return list
})

// 按日期分组
const groupedSessions = computed(() => {
  const groups = {}
  // 使用本地时间，与 mtime 保持一致
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const yd = new Date(Date.now() - 86400000)
  const yesterday = `${yd.getFullYear()}-${pad(yd.getMonth() + 1)}-${pad(yd.getDate())}`
  const wa = new Date(Date.now() - 7 * 86400000)
  const weekAgo = `${wa.getFullYear()}-${pad(wa.getMonth() + 1)}-${pad(wa.getDate())}`

  // 先按是否有拒绝内容排序，再按日期分组
  const sortedSessions = [...filteredSessions.value].sort((a, b) => {
    // 有拒绝内容的排前面
    if (a.has_refusal !== b.has_refusal) {
      return a.has_refusal ? -1 : 1
    }
    // 同类型按修改时间排序
    return b.mtime.localeCompare(a.mtime)
  })

  for (const session of sortedSessions) {
    // 用 mtime（最后修改时间）分组，而非文件名中的创建日期
    const mtimeDate = session.mtime.split(' ')[0]  // "2026-03-27 03:21:00" → "2026-03-27"
    let label
    if (mtimeDate === today) {
      label = t('session.today')
    } else if (mtimeDate === yesterday) {
      label = t('session.yesterday')
    } else if (mtimeDate >= weekAgo) {
      label = t('session.thisWeek')
    } else {
      label = t('session.earlier')
    }

    if (!groups[label]) {
      groups[label] = []
    }
    groups[label].push(session)
  }

  const order = [t('session.today'), t('session.yesterday'), t('session.thisWeek'), t('session.earlier')]
  return order
    .filter(label => groups[label])
    .map(label => ({
      label,
      sessions: groups[label]
    }))
})

function selectSession(id) {
  sessionStore.selectSession(id)
}

function toggleExpand(id) {
  if (expandedIds.has(id)) {
    expandedIds.delete(id)
  } else {
    expandedIds.add(id)
  }
}

function toggleGroup(label) {
  if (expandedGroups.has(label)) {
    expandedGroups.delete(label)
  } else {
    expandedGroups.add(label)
  }
}

async function refresh() {
  loading.value = true
  try {
    await sessionStore.fetchSessions()
  } finally {
    loading.value = false
  }
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(mtime) {
  const parts = mtime.split(' ')
  return parts.length > 1 ? parts[1].slice(0, 5) : mtime
}
</script>

<style scoped>
.session-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  flex-shrink: 0;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1, #fff);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.format-tabs {
  flex-shrink: 0;
  display: flex;
  overflow-x: auto;
  scrollbar-width: none;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.format-tabs::-webkit-scrollbar {
  display: none;
}

.format-tab {
  flex-shrink: 0;
  padding: 8px 16px;
  font-size: 13px;
  white-space: nowrap;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-text-3, #888);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: color 0.2s, border-color 0.2s;
  margin-bottom: -1px;
}

.format-tab:hover {
  color: var(--color-text-2, #ccc);
}

.format-tab.active {
  color: var(--color-text-1, #fff);
  border-bottom-color: #18a058;
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--color-bg-3, #3a3a3a);
  border-radius: 9px;
  font-size: 11px;
  line-height: 1;
}

.format-tab.active .tab-count {
  background: rgba(24, 160, 88, 0.25);
  color: #18a058;
}

.filter-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px 12px;
}

.search-box {
  flex-shrink: 0;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.filter-tabs {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
}

.list-scrollbar {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 48px; /* 日志面板收起高度 + 安全边距 */
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.list-content {
  padding: 8px 0;
}

.date-group {
  margin-bottom: 8px;
}

.date-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-3, #888);
  cursor: pointer;
  user-select: none;
}

.date-label:hover {
  color: var(--color-text-2, #aaa);
}

.group-icon {
  transition: transform 0.2s;
  font-size: 12px;
}

.group-icon.expanded {
  transform: rotate(0deg);
}

.group-icon:not(.expanded) {
  transform: rotate(-90deg);
}

.date-label .count {
  margin-left: auto;
  background: var(--color-bg-3, #3a3a3a);
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
}

.group-sessions {
  overflow: hidden;
}

.session-item {
  padding: 8px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light, #2a2a2a);
  transition: background 0.2s;
}

.session-item:hover {
  background: var(--color-bg-2, #2a2a2a);
}

.session-item.selected {
  background: #2d4a3a;
}

/* 有拒绝内容的会话 - 高亮显示 */
.session-item.has-refusal {
  background: rgba(208, 48, 80, 0.1);
  border-left: 3px solid #d03050;
}

.session-item.has-refusal:hover {
  background: rgba(208, 48, 80, 0.15);
}

.session-item.has-refusal.selected {
  background: rgba(208, 48, 80, 0.2);
}

.session-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-id {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1, #fff);
  font-family: monospace;
}

.session-time {
  font-size: 11px;
  color: var(--color-text-4, #666);
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  transition: transform 0.2s;
  color: var(--color-text-3, #888);
  cursor: pointer;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.session-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border, #3a3a3a);
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.detail-item .label {
  color: var(--color-text-3, #888);
  min-width: 60px;
}

.detail-item .value {
  color: var(--color-text-2, #ccc);
  font-family: monospace;
}
</style>
