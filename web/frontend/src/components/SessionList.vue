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
        @keyup.enter="handleSearch"
        @clear="handleClearSearch"
      >
        <template #prefix>
          <n-icon><SearchOutline /></n-icon>
        </template>
      </n-input>
      <n-button size="small" type="primary" @click="handleSearch" :loading="loading" style="margin-left: 8px">
        {{ $t('session.searchBtn') }}
      </n-button>
    </div>

    <!-- 搜索模式提示 -->
    <div v-if="sessionStore.isSearchMode" class="search-mode-hint">
      <n-text depth="3" style="font-size: 12px">{{ $t('session.searchModeHint', { count: visibleSessions.length }) }}</n-text>
      <n-button text size="tiny" type="primary" @click="handleClearSearch" style="font-size: 12px; margin-left: 8px">
        {{ $t('session.clearSearch') }}
      </n-button>
    </div>

    <!-- 过滤标签 -->
    <div class="filter-tabs">
      <n-button
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
        {{ $t('session.needsClean') }} {{ refusalCount }}
      </n-button>
      <n-button
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
          <n-text depth="3" style="font-size: 12px">{{ $t('session.filteredHidden', { count: visibleSessions.length }) }}</n-text>
          <n-button text size="tiny" type="primary" @click="filterMode = 'all'" style="font-size: 12px">
            {{ $t('session.showAll') }}
          </n-button>
        </div>

        <!-- Codex 优先按项目/工作区分组；其他工具或搜索模式保持日期视图 -->
        <div v-for="group in groupedSessions" :key="group.key" class="date-group">
          <div class="date-label project-label" @click="toggleGroup(group.key)">
            <n-icon class="group-icon" :class="{ expanded: expandedGroups.has(group.key) }">
              <ChevronDownOutline />
            </n-icon>
            <div class="group-title-wrap">
              <span>{{ group.label }}</span>
              <span v-if="group.subtitle" class="group-subtitle" :title="group.subtitle">{{ group.subtitle }}</span>
            </div>
            <n-tag v-if="group.needsCleanCount > 0" type="error" size="tiny" :bordered="false">
              {{ $t('session.needsClean') }} {{ group.needsCleanCount }}
            </n-tag>
            <span class="count">{{ group.sessions.length }}</span>
          </div>

          <div v-show="expandedGroups.has(group.key)" class="group-sessions">
            <div
              v-for="session in group.sessions"
              :key="session.id"
              class="session-item"
              :class="[
                sessionStateClass(session),
                { selected: session.id === sessionStore.selectedId }
              ]"
            >
              <div class="session-main" @click="selectSession(session.id)">
                <div class="session-info">
                  <div class="session-title-line">
                    <span class="session-title" :title="session.title || session.id">{{ sessionDisplayTitle(session) }}</span>
                    <n-tag
                      v-if="session.format === 'codex'"
                      :type="session.ctf_active ? 'success' : 'default'"
                      size="tiny"
                      :bordered="false"
                    >
                      {{ session.ctf_active ? $t('session.ctfActive') : $t('session.ctfInactive') }}
                    </n-tag>
                    <n-tag
                      :type="sessionStateType(session)"
                      size="tiny"
                      :bordered="false"
                    >
                      {{ sessionStateLabel(session) }}
                    </n-tag>
                  </div>
                  <div class="session-subtitle">
                    <span class="session-time">{{ formatTime(session.mtime) }}</span>
                    <span class="session-id">#{{ session.id }}</span>
                  </div>
                  <div class="session-snippet" :title="session.last_user_message || session.first_user_message || session.last_assistant_message || ''">
                    {{ sessionSnippet(session) }}
                  </div>
                  <div class="session-action-inline" :class="sessionStateClass(session)">
                    {{ sessionActionShort(session) }}
                  </div>
                </div>
                <div class="session-meta">
                  <n-button
                    size="tiny"
                    quaternary
                    type="error"
                    :title="$t('session.deleteSession')"
                    :loading="deletingId === session.id"
                    @click.stop="confirmDeleteSession(session)"
                  >
                    {{ $t('common.delete') }}
                  </n-button>
                  <n-tag
                    v-if="session.has_refusal"
                    type="error"
                    size="small"
                  >
                    {{ $t('session.refusalCount', { count: session.refusal_count }) }}
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
                <div v-if="session.format === 'codex'" class="detail-item">
                  <span class="label">{{ $t('session.ctfStatus') }}:</span>
                  <span class="value action-value">
                    {{ session.ctf_active ? $t('session.ctfActiveDetail') : $t('session.ctfInactiveDetail') }}
                  </span>
                </div>
                <div class="detail-item">
                  <span class="label">{{ $t('session.nextAction') }}:</span>
                  <span class="value action-value">{{ sessionActionHint(session) }}</span>
                </div>
                <div v-if="session.first_user_message" class="detail-item detail-block">
                  <span class="label">{{ $t('session.firstUserMessage') }}:</span>
                  <span class="value action-value">{{ session.first_user_message }}</span>
                </div>
                <div v-if="session.last_user_message && session.last_user_message !== session.first_user_message" class="detail-item detail-block">
                  <span class="label">{{ $t('session.lastUserMessage') }}:</span>
                  <span class="value action-value">{{ session.last_user_message }}</span>
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
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage, useDialog } from 'naive-ui'
import { RefreshOutline, ChevronDownOutline, SearchOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'
import { useSettingsStore } from '../stores/settingsStore'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
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
const filterMode = ref('all')  // 'all' | 'refusal' | 'clean' | 'patched'
const loading = ref(false)
const deletingId = ref(null)
let selectingVisibleSession = false

// 防抖定时器
let searchDebounceTimer = null

// 搜索处理（带防抖）
async function handleSearch() {
  if (!searchQuery.value || !searchQuery.value.trim()) {
    return
  }
  // 清除之前的定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 300ms 防抖
  searchDebounceTimer = setTimeout(async () => {
    loading.value = true
    try {
      await sessionStore.searchSessions(searchQuery.value.trim())
    } finally {
      loading.value = false
    }
  }, 300)
}

// 清除搜索
async function handleClearSearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchQuery.value = ''
  await sessionStore.clearSearch()
}

// 组件销毁时清理定时器
onUnmounted(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
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
  // 搜索模式下，服务端已过滤，直接返回
  if (sessionStore.isSearchMode) {
    return visibleSessions.value
  }
  let list = visibleSessions.value
  // 按拒绝状态过滤
  if (filterMode.value === 'refusal') {
    list = list.filter(s => s.has_refusal)
  } else if (filterMode.value === 'clean') {
    list = list.filter(s => !s.has_refusal)
  } else if (filterMode.value === 'patched') {
    list = list.filter(s => s.has_backup)
  }
  return list
})

// 保持左侧可见列表与右侧预览一致：
// 默认过滤是“需要清理”，如果仍预览全部会话里的最新会话，会造成“左侧 A、右侧 B”的误解。
watch(
  () => filteredSessions.value.map(s => s.id).join('|'),
  async () => {
    if (selectingVisibleSession || loading.value) return
    const list = filteredSessions.value
    if (list.length === 0) return
    const selectedVisible = list.some(s => s.id === sessionStore.selectedId)
    if (selectedVisible) return

    selectingVisibleSession = true
    try {
      await sessionStore.selectSession(list[0].id)
    } finally {
      selectingVisibleSession = false
    }
  },
  { immediate: true }
)

const shouldGroupByCtfAndProject = computed(() =>
  sessionStore.activeTab === 'codex' && !sessionStore.isSearchMode
)

function projectNameFromPath(path) {
  if (!path) return ''
  const normalized = String(path).replace(/[\\/]+$/, '')
  const parts = normalized.split(/[\\/]/)
  return parts[parts.length - 1] || normalized
}

function projectGroupLabel(session) {
  return session.project_name || projectNameFromPath(session.project_path) || t('session.unknownProject')
}

function ensureProjectGroupsExpanded(groups) {
  if (!shouldGroupByCtfAndProject.value) return
  for (const group of groups.slice(0, 8)) {
    expandedGroups.add(group.key)
  }
}

// 按项目或日期分组
const groupedSessions = computed(() => {
  if (shouldGroupByCtfAndProject.value) {
    const groups = {}
    const sortedSessions = [...filteredSessions.value].sort((a, b) => {
      if (a.has_refusal !== b.has_refusal) return a.has_refusal ? -1 : 1
      if (a.ctf_active !== b.ctf_active) return a.ctf_active ? -1 : 1
      return b.mtime.localeCompare(a.mtime)
    })

    for (const session of sortedSessions) {
      const ctfBucket = session.ctf_active ? 'ctf-active' : 'ctf-normal'
      const projectKey = session.project_key || session.project_path || '__unknown__'
      const key = `${ctfBucket}:${projectKey}`
      if (!groups[key]) {
        const ctfLabel = session.ctf_active ? t('session.ctfGroupActive') : t('session.ctfGroupNormal')
        groups[key] = {
          key,
          label: `${ctfLabel} · ${projectGroupLabel(session)}`,
          subtitle: session.project_path || '',
          sessions: [],
          needsCleanCount: 0,
          ctfActive: session.ctf_active,
        }
      }
      groups[key].sessions.push(session)
      if (session.has_refusal) groups[key].needsCleanCount += 1
    }

    const result = Object.values(groups).sort((a, b) => {
      if (a.needsCleanCount !== b.needsCleanCount) return b.needsCleanCount - a.needsCleanCount
      if (a.ctfActive !== b.ctfActive) return a.ctfActive ? -1 : 1
      const at = a.sessions[0]?.mtime || ''
      const bt = b.sessions[0]?.mtime || ''
      return bt.localeCompare(at)
    })
    ensureProjectGroupsExpanded(result)
    return result
  }

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
      key: label,
      label,
      subtitle: '',
      sessions: groups[label],
      needsCleanCount: groups[label].filter(s => s.has_refusal).length,
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

function confirmDeleteSession(session) {
  dialog.warning({
    title: t('session.deleteSession'),
    content: t('session.deleteSessionConfirm', {
      title: sessionDisplayTitle(session),
      id: session.id,
    }),
    positiveText: t('session.deleteSessionConfirmButton'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      deletingId.value = session.id
      try {
        const result = await sessionStore.deleteSession(session.id)
        if (result.success) {
          message.success(result.message || t('session.deleteSessionSuccess'))
          expandedIds.delete(session.id)
        } else {
          message.error(result.message || t('session.deleteSessionFailed'))
        }
      } catch (error) {
        message.error(error.message || t('session.deleteSessionFailed'))
      } finally {
        deletingId.value = null
      }
    },
  })
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

function sessionDisplayTitle(session) {
  const title = session.title || session.first_user_message || session.last_user_message || session.id
  return truncate(title, 42)
}

function sessionSnippet(session) {
  const text = session.last_user_message || session.first_user_message || session.last_assistant_message
  if (!text) return session.project_path ? truncate(session.project_path, 44) : t('session.noConversation')
  return truncate(text, 58)
}

function sessionStateType(session) {
  if (session.has_refusal) return 'error'
  if (session.has_backup) return 'success'
  return 'default'
}

function sessionStateLabel(session) {
  if (session.has_refusal) return t('session.needsClean')
  if (session.has_backup) return t('session.cleaned')
  return t('session.noActionNeeded')
}

function sessionStateClass(session) {
  if (session.has_refusal) return 'needs-clean'
  if (session.has_backup) return 'cleaned'
  return 'normal'
}

function sessionActionHint(session) {
  if (session.has_refusal) return t('session.actionCleanHint')
  if (session.has_backup) return t('session.actionReviewHint')
  return t('session.actionNoNeedHint')
}

function sessionActionShort(session) {
  if (session.has_refusal) return t('session.actionCleanShort', { count: session.refusal_count || 1 })
  if (session.has_backup) return t('session.actionReviewShort')
  return t('session.actionNoNeedShort')
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
  display: flex;
  align-items: center;
}

.search-mode-hint {
  flex-shrink: 0;
  padding: 6px 12px;
  background: rgba(32, 128, 240, 0.1);
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  display: flex;
  align-items: center;
  justify-content: center;
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

.project-label {
  gap: 8px;
}

.group-title-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.group-subtitle {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-4, #666);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.session-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.session-title-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.session-id {
  font-size: 11px;
  color: var(--color-text-4, #666);
  font-family: monospace;
}

.session-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-1, #fff);
}

.session-subtitle {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.session-time {
  font-size: 11px;
  color: var(--color-text-4, #666);
}

.session-snippet {
  margin-top: 2px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-3, #888);
}

.session-action-inline {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
}

.session-action-inline.needs-clean {
  color: #ff8a9a;
}

.session-action-inline.cleaned {
  color: #63d392;
}

.session-action-inline.normal {
  color: var(--color-text-3, #888);
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
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
  min-width: 74px;
}

.detail-item .value {
  color: var(--color-text-2, #ccc);
  font-family: monospace;
}

.detail-item.detail-block {
  align-items: flex-start;
}

.detail-item .action-value {
  font-family: inherit;
  color: var(--color-text-1, #fff);
}

.session-item.needs-clean {
  background: rgba(208, 48, 80, 0.1);
  border-left: 3px solid #d03050;
}

.session-item.needs-clean:hover {
  background: rgba(208, 48, 80, 0.15);
}

.session-item.needs-clean.selected {
  background: rgba(208, 48, 80, 0.22);
}

.session-item.cleaned {
  border-left: 3px solid #18a058;
}

.session-item.cleaned.selected {
  background: rgba(24, 160, 88, 0.18);
}
</style>
