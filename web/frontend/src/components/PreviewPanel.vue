<template>
  <div class="preview-panel">
    <div v-if="!session" class="empty-state">
      <n-empty :description="$t('session.selectPrompt')" />
    </div>

    <div v-else-if="!preview" class="empty-state">
      <n-spin size="large" />
    </div>

    <div v-else class="preview-container">
      <div class="session-action-summary" :class="summaryClass">
        <div class="summary-content">
          <div class="summary-main">
            <n-tag :type="summaryTagType" size="small" :bordered="false">
              {{ summaryTitle }}
            </n-tag>
            <span>{{ summaryText }}</span>
          </div>
          <div class="summary-session-context">
            <strong>{{ session.project_name || projectNameFromPath(session.project_path) || $t('session.unknownProject') }}</strong>
            <span v-if="session.title">· {{ session.title }}</span>
            <span class="summary-session-id">#{{ session.id }}</span>
          </div>
        </div>
        <div class="summary-tags">
          <n-tag
            v-if="session.format === 'codex'"
            :type="session.ctf_active ? 'success' : 'default'"
            size="small"
            :bordered="false"
          >
            {{ session.ctf_active ? $t('session.ctfActive') : $t('session.ctfInactive') }}
          </n-tag>
          <n-tag v-if="session.has_refusal" type="error" size="small" :bordered="false">
            {{ $t('session.refusalCount', { count: session.refusal_count || cleanableRefusalCount }) }}
          </n-tag>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="preview-tabs">
        <div
          class="tab-item"
          :class="{ active: activeTab === 'changes' }"
          @click="activeTab = 'changes'"
        >
          <n-icon><SwapHorizontalOutline /></n-icon>
          <span>{{ $t('preview.changes') }}</span>
          <n-tag v-if="preview.has_changes" type="warning" size="small" style="margin-left: 4px">
            {{ preview.changes.length }}
          </n-tag>
        </div>
        <div
          class="tab-item"
          :class="{ active: activeTab === 'diff' }"
          @click="activeTab = 'diff'"
        >
          <n-icon><CodeOutline /></n-icon>
          <span>{{ $t('preview.diff') }}</span>
        </div>
      </div>

      <!-- 修改预览 Tab -->
      <div v-show="activeTab === 'changes'" class="preview-scrollbar">
        <div v-if="sessionStore.aiRewriteLoading || sessionStore.autoRewriteNotice" class="auto-rewrite-banner" :class="sessionStore.autoRewriteNotice?.type || 'info'">
          <n-icon><SparklesOutline /></n-icon>
          <span>
            {{ sessionStore.aiRewriteLoading ? $t('action.aiRewriteRunning') : sessionStore.autoRewriteNotice.message }}
          </span>
        </div>
        <!-- 无拒绝内容时显示对话摘要 -->
        <div v-if="!preview.changes || preview.changes.length === 0" class="no-refusal-content">
          <!-- 状态提示 -->
          <div class="status-banner success-banner" v-if="!preview.has_changes">
            <n-icon color="#18a058"><CheckmarkCircleOutline /></n-icon>
            <span>{{ $t('preview.noRefusal') }}</span>
          </div>
          <div class="status-banner info-banner" v-if="preview.reasoning_count > 0">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="emit('update:cleanReasoning', $event)"
            />
            <n-icon color="#2080f0"><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteReasoning', { count: preview.reasoning_count }) }}</span>
          </div>
          <div class="status-banner info-banner thinking-banner-inline" v-if="preview.thinking_count > 0">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="emit('update:cleanReasoning', $event)"
            />
            <n-icon color="#8b5cf6"><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteThinking', { count: preview.thinking_count }) }}</span>
          </div>

          <!-- 对话摘要 -->
          <div v-if="preview.conversation_summary && preview.conversation_summary.length > 0" class="conversation-summary">
            <div class="summary-header">
              <span>{{ $t('preview.conversation') }}</span>
              <n-tag size="small" :bordered="false">{{ preview.total_turns }} {{ $t('preview.turns') }}</n-tag>
            </div>
            <div class="summary-list">
              <div
                v-for="(turn, idx) in preview.conversation_summary"
                :key="idx"
                class="summary-turn"
                :class="turn.role"
              >
                <div class="turn-header">
                  <n-tag
                    :type="turn.role === 'user' ? 'info' : 'default'"
                    size="small"
                    :bordered="false"
                  >
                    {{ turn.role === 'user' ? 'User' : 'Assistant' }}
                  </n-tag>
                  <span class="turn-line">L{{ turn.line_num }}</span>
                </div>
                <pre class="turn-content">{{ turn.content }}</pre>
              </div>
            </div>
          </div>
          <div v-else class="empty-content">
            <n-empty :description="$t('preview.noConversation')" />
          </div>
        </div>

        <div v-else class="preview-content">
          <!-- 推理内容提示 -->
          <div v-if="preview.reasoning_count > 0" class="reasoning-banner">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="$emit('update:cleanReasoning', $event)"
            />
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteReasoning', { count: preview.reasoning_count }) }}</span>
          </div>

          <!-- Thinking Block 提示 -->
          <div v-if="preview.thinking_count > 0" class="thinking-banner">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="$emit('update:cleanReasoning', $event)"
            />
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteThinking', { count: preview.thinking_count }) }}</span>
          </div>

          <!-- 选择操作栏 -->
          <div v-if="preview.changes && preview.changes.length > 1" class="select-toolbar">
            <n-checkbox :checked="isAllSelected" @update:checked="toggleSelectAll" />
            <span class="select-label">
              {{ $t('preview.selectedCount', { selected: selectedLines.size, total: preview.changes.length }) }}
            </span>
            <n-button text size="tiny" type="primary" @click="toggleSelectAll">
              {{ isAllSelected ? $t('preview.deselectAll') : $t('preview.selectAll') }}
            </n-button>
          </div>

          <div class="changes-list">
            <div
              v-for="(change, index) in preview.changes"
              :key="index"
              class="change-item"
              :class="{ unselected: !selectedLines.has(change.line_num) }"
            >
              <div class="change-header">
                <n-checkbox
                  :checked="selectedLines.has(change.line_num)"
                  @update:checked="toggleLine(change.line_num)"
                />
                <n-tag
                  :type="changeTagType(change.type)"
                  size="small"
                >
                  {{ changeTagLabel(change.type) }}
                </n-tag>
                <span class="line-num">
                  <template v-if="change.line_nums && change.line_nums.length > 1">
                    {{ change.line_nums.map(n => 'L' + n).join(' ') }}
                  </template>
                  <template v-else>L{{ change.line_num }}</template>
                </span>
              </div>

              <div v-if="change.type === 'replace'" class="change-content">
                <div class="content-block original">
                  <div class="content-label">{{ $t('preview.original') }}</div>
                  <pre>{{ change.original }}</pre>
                </div>
                <div class="content-arrow">
                  <n-icon size="20" color="#18a058">
                    <ArrowDownOutline />
                  </n-icon>
                </div>
                <div class="content-block replacement">
                  <div class="content-label">
                    {{ $t('preview.replacement') }}
                    <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px">AI</n-tag>
                  </div>
                  <pre>{{ change.replacement }}</pre>
                </div>
              </div>

              <div v-else-if="change.type === 'remove_thinking'" class="change-content">
                <div class="content-block thinking">
                  <div class="content-label">{{ $t('preview.removeThinking') }}</div>
                  <pre>{{ change.content || '(Thinking block)' }}</pre>
                </div>
              </div>

              <div v-else class="change-content">
                <div class="content-block deleted">
                  <div class="content-label">{{ $t('preview.deleted') }}</div>
                  <pre>{{ change.content }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Diff 视图 Tab -->
      <div v-show="activeTab === 'diff'" class="preview-scrollbar">
        <!-- 已清理会话：显示清理前后对比 -->
        <div v-if="preview.diff_items && preview.diff_items.length > 0" class="diff-content">
          <div class="diff-header-banner">
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.diffWithBackup') }}</span>
          </div>
          <div
            v-for="(item, index) in preview.diff_items"
            :key="'backup-' + index"
            class="diff-block"
          >
            <div class="diff-line deleted">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ item.before }}</pre>
            </div>
            <div class="diff-line added">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">+</span>
              <pre class="diff-text">{{ item.after }}</pre>
            </div>
          </div>
        </div>

        <!-- 未清理会话：显示待修改的 diff -->
        <div v-else-if="preview.has_changes" class="diff-content">
          <div
            v-for="(change, index) in preview.changes"
            :key="index"
            class="diff-block"
          >
            <!-- 删除行 -->
            <div v-if="change.type === 'delete'" class="diff-line deleted">
              <span class="line-number">{{ change.line_num }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ change.content || $t('preview.reasoningBlocks') }}</pre>
            </div>

            <!-- 移除 Thinking Block -->
            <div v-else-if="change.type === 'remove_thinking'" class="diff-line thinking-removed">
              <span class="line-number">{{ change.line_num }}</span>
              <span class="diff-marker">~</span>
              <pre class="diff-text">{{ change.content || '[Thinking Block]' }}</pre>
            </div>

            <!-- 替换：显示删除和新增 -->
            <template v-else-if="change.type === 'replace'">
              <div class="diff-line deleted">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">-</span>
                <pre class="diff-text">{{ change.original }}</pre>
              </div>
              <div class="diff-line added">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">+</span>
                <pre class="diff-text">{{ change.replacement }}</pre>
                <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px; flex-shrink: 0">AI</n-tag>
              </div>
            </template>
          </div>
        </div>

        <div v-else class="empty-content">
          <n-empty :description="$t('preview.noChanges')" type="success">
            <template #icon>
              <n-icon size="48" color="#18a058">
                <CheckmarkCircleOutline />
              </n-icon>
            </template>
          </n-empty>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckmarkCircleOutline, ArrowDownOutline, SwapHorizontalOutline, CodeOutline, InformationCircleOutline, SparklesOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'

const { t } = useI18n()
const sessionStore = useSessionStore()
const activeTab = ref('changes')

// 接收 cleanReasoning prop
const props = defineProps({
  cleanReasoning: {
    type: Boolean,
    default: true
  }
})

// 定义 emit
const emit = defineEmits(['update:cleanReasoning'])

// 选中的行号集合
const selectedLines = ref(new Set())

const session = computed(() => sessionStore.getSelectedSession())
const preview = computed(() => sessionStore.preview)

const refusalChangeCount = computed(() => preview.value?.changes?.length || 0)
const hasRefusalChanges = computed(() =>
  refusalChangeCount.value > 0 || (session.value?.has_refusal && (session.value?.refusal_count || 0) > 0)
)

const hasCleanableThinking = computed(() => {
  const p = preview.value
  return (p?.reasoning_count || 0) > 0 || (p?.thinking_count || 0) > 0
})

const summaryTagType = computed(() => {
  if (hasRefusalChanges.value) return 'error'
  if (hasCleanableThinking.value) return 'warning'
  if (session.value?.has_backup) return 'success'
  return 'success'
})

const summaryClass = computed(() => {
  if (hasRefusalChanges.value) return 'needs-clean-summary'
  if (hasCleanableThinking.value) return 'thinking-summary'
  return 'ok-summary'
})

const summaryTitle = computed(() => {
  if (hasRefusalChanges.value) return t('session.needsClean')
  if (hasCleanableThinking.value) return t('preview.cleanReasoning')
  if (session.value?.has_backup) return t('session.cleaned')
  return t('session.noActionNeeded')
})

const summaryText = computed(() => {
  if (hasRefusalChanges.value) {
    return t('preview.actionCleanNow', { count: cleanableRefusalCount.value })
  }
  if (hasCleanableThinking.value) {
    const count = (preview.value?.reasoning_count || 0) + (preview.value?.thinking_count || 0)
    return t('preview.actionCleanThinkingNow', { count })
  }
  if (session.value?.has_backup) return t('preview.actionReviewDiff')
  return t('preview.actionNoNeed')
})

const cleanableRefusalCount = computed(() => {
  const previewCount = refusalChangeCount.value
  const sessionCount = session.value?.refusal_count || 0
  return Math.max(previewCount, sessionCount)
})

// 监听预览数据变化，初始化选中状态（默认全选）
watch(() => sessionStore.preview, (newPreview) => {
  if (newPreview?.changes?.length) {
    selectedLines.value = new Set(newPreview.changes.map(c => c.line_num))
  } else {
    selectedLines.value = new Set()
  }
}, { immediate: true })

// 全选/取消全选
function toggleSelectAll() {
  if (!preview.value?.changes?.length) return
  if (selectedLines.value.size === preview.value.changes.length) {
    selectedLines.value = new Set()
  } else {
    selectedLines.value = new Set(preview.value.changes.map(c => c.line_num))
  }
}

// 切换单个选择
function toggleLine(lineNum) {
  const newSet = new Set(selectedLines.value)
  if (newSet.has(lineNum)) {
    newSet.delete(lineNum)
  } else {
    newSet.add(lineNum)
  }
  selectedLines.value = newSet
}

// 是否全选
const isAllSelected = computed(() => {
  if (!preview.value?.changes?.length) return false
  return selectedLines.value.size === preview.value.changes.length
})

// 获取选中的行号列表
function getSelectedLines() {
  return Array.from(selectedLines.value)
}

// 暴露方法给父组件
defineExpose({
  getSelectedLines,
  hasChanges: () => hasRefusalChanges.value,
  changesCount: () => refusalChangeCount.value,
  selectedCount: () => selectedLines.value.size
})

function changeTagType(type) {
  if (type === 'replace') return 'warning'
  if (type === 'remove_thinking') return 'info'
  return 'error'
}

function changeTagLabel(type) {
  if (type === 'replace') return t('preview.replace')
  if (type === 'remove_thinking') return t('preview.removeThinking')
  return t('preview.delete')
}

function projectNameFromPath(path) {
  if (!path) return ''
  const normalized = String(path).replace(/[\\/]+$/, '')
  const parts = normalized.split(/[\\/]/)
  return parts[parts.length - 1] || normalized
}

// 已清理会话（有备份）默认显示 Diff 视图
watch(() => sessionStore.selectedId, () => {
  const s = sessionStore.getSelectedSession()
  // 有新拒绝内容时优先显示修改预览；只有备份且无新拒绝才显示 Diff
  if (s?.has_backup && !s?.has_refusal) {
    activeTab.value = 'diff'
  } else {
    activeTab.value = 'changes'
  }
})
</script>

<style scoped>
.preview-panel {
  flex: 1;
  overflow: hidden;
  background: var(--color-bg-1, #1a1a1a);
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.empty-state {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.preview-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  padding: 0 16px;
  flex-shrink: 0;
}

.session-action-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  font-size: 13px;
}

.summary-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.summary-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.summary-session-context {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-3, #888);
  font-size: 12px;
}

.summary-session-id {
  margin-left: 6px;
  color: var(--color-text-4, #666);
  font-family: monospace;
}

.summary-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.session-action-summary.needs-clean-summary {
  background: rgba(208, 48, 80, 0.12);
}

.session-action-summary.thinking-summary {
  background: rgba(240, 160, 32, 0.12);
}

.session-action-summary.ok-summary {
  background: rgba(24, 160, 88, 0.1);
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--color-text-3, #888);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}

.tab-item:hover {
  color: var(--color-text-2, #ccc);
}

.tab-item.active {
  color: var(--color-primary, #18a058);
  border-bottom-color: var(--color-primary, #18a058);
}

.preview-scrollbar {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.auto-rewrite-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin: 12px 16px 0;
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.auto-rewrite-banner.info {
  background: rgba(32, 128, 240, 0.14);
}

.auto-rewrite-banner.success {
  background: rgba(24, 160, 88, 0.14);
}

.auto-rewrite-banner.warning {
  background: rgba(240, 160, 32, 0.16);
}

.empty-content {
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-content {
  padding: 16px;
}

.changes-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.change-item {
  background: var(--color-bg-2, #2d2d2d);
  border-radius: 8px;
  padding: 12px;
}

.change-item.unselected {
  opacity: 0.5;
}

.change-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.select-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--color-bg-2, #2d2d2d);
  border-radius: 6px;
  margin-bottom: 12px;
}

.select-label {
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.line-num {
  font-size: 12px;
  color: var(--color-text-3, #888);
  font-family: monospace;
}

.change-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.content-block {
  padding: 12px;
  border-radius: 6px;
}

.content-block.original {
  background: #3d2d2d;
  border-left: 3px solid #d03050;
}

.content-block.replacement {
  background: #2d3d2d;
  border-left: 3px solid #18a058;
}

.content-block.deleted {
  background: #3d2d2d;
  border-left: 3px solid #909090;
}

.content-label {
  font-size: 11px;
  color: var(--color-text-3, #888);
  margin-bottom: 8px;
  text-transform: uppercase;
}

.content-block pre {
  font-size: 13px;
  color: var(--color-text-2, #ccc);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}

.content-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
}

/* Diff 视图样式 */
.diff-content {
  padding: 16px;
  font-family: 'Fira Code', 'SF Mono', Monaco, monospace;
}

.diff-block {
  margin-bottom: 8px;
}

.diff-line {
  display: flex;
  align-items: flex-start;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.5;
}

.diff-line.deleted {
  background: rgba(208, 48, 80, 0.15);
}

.diff-line.added {
  background: rgba(24, 160, 88, 0.15);
}

.line-number {
  min-width: 40px;
  padding: 0 8px;
  color: var(--color-text-4, #666);
  text-align: right;
  user-select: none;
}

.diff-marker {
  min-width: 20px;
  text-align: center;
  font-weight: bold;
}

.diff-line.deleted .diff-marker {
  color: #d03050;
}

.diff-line.added .diff-marker {
  color: #18a058;
}

.diff-text {
  flex: 1;
  margin: 0;
  padding: 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text-2, #ccc);
}

/* Diff 头部横幅 */
.diff-header-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

/* Thinking Block 内容块 */
.content-block.thinking {
  background: #2d2d3d;
  border-left: 3px solid #7b68ee;
}

/* Thinking Block 提示 */
.thinking-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(123, 104, 238, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.thinking-banner .n-checkbox {
  flex-shrink: 0;
}

/* Diff 视图 Thinking Block 移除 */
.diff-line.thinking-removed {
  background: rgba(123, 104, 238, 0.15);
}

.diff-line.thinking-removed .diff-marker {
  color: #7b68ee;
}

/* 推理内容提示 */
.reasoning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.reasoning-banner .n-checkbox {
  flex-shrink: 0;
}

.reasoning-info {
  text-align: center;
  line-height: 1.6;
}

.reasoning-info strong {
  color: #2080f0;
  font-weight: 600;
}

/* 无拒绝内容区域 */
.no-refusal-content {
  padding: 16px;
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.status-banner .n-checkbox {
  flex-shrink: 0;
}

.status-banner.success-banner {
  background: rgba(24, 160, 88, 0.12);
}

.status-banner.info-banner {
  background: rgba(32, 128, 240, 0.12);
}

/* 对话摘要 */
.conversation-summary {
  margin-top: 8px;
}

.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-2, #ccc);
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  margin-bottom: 8px;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-turn {
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--color-bg-2, #2d2d2d);
}

.summary-turn.user {
  border-left: 3px solid #2080f0;
}

.summary-turn.assistant {
  border-left: 3px solid #18a058;
}

.turn-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.turn-line {
  font-size: 11px;
  color: var(--color-text-4, #666);
  font-family: monospace;
}

.turn-content {
  font-size: 12px;
  color: var(--color-text-2, #ccc);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}
</style>
