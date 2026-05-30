<template>
  <div class="action-bar">
    <div class="left-actions">
      <n-button
        :type="hasRefusalOnly ? 'error' : 'warning'"
        :disabled="!canPatch || sessionStore.aiRewriteLoading"
        :loading="patching || sessionStore.aiRewriteLoading"
        @click="handlePatch"
      >
        <template #icon>
          <n-icon><TrashOutline /></n-icon>
        </template>
        {{ cleanButtonLabel }}
      </n-button>

      <n-button
        v-if="hasRefusalOnly"
        secondary
        :disabled="!canAIRewrite"
        :loading="sessionStore.aiRewriteLoading"
        @click="handleAIAnalyze"
      >
        <template #icon>
          <n-icon><SparklesOutline /></n-icon>
        </template>
        {{ sessionStore.aiRewrite ? $t('action.aiRewriteReady') : $t('action.aiRewriteNow') }}
        <n-tag v-if="!settingsStore.aiEnabled" size="small" type="info" style="margin-left: 4px">{{ $t('enhance.ctfNotInstalled') }}</n-tag>
        <n-tag v-else-if="sessionStore.aiRewrite" size="small" type="success" style="margin-left: 4px">✓</n-tag>
      </n-button>

      <n-button
        :disabled="!canRestore"
        :loading="restoring"
        @click="handleRestore"
      >
        <template #icon>
          <n-icon><ArrowUndoOutline /></n-icon>
        </template>
        {{ $t('action.restore') }}
      </n-button>
    </div>

    <div class="right-info">
      <n-tag v-if="sessionStore.aiRewriteLoading" type="info">
        {{ $t('action.aiRewriteRunning') }}
      </n-tag>
      <n-tag v-else-if="sessionStore.autoRewriteNotice" :type="sessionStore.autoRewriteNotice.type">
        {{ sessionStore.autoRewriteNotice.message }}
      </n-tag>
      <n-tag v-if="lastResult" :type="lastResult.type">
        {{ lastResult.message }}
      </n-tag>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage, useDialog, NSelect } from 'naive-ui'
import { TrashOutline, SparklesOutline, ArrowUndoOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'
import { useLogStore } from '../stores/logStore'
import { useSettingsStore } from '../stores/settingsStore'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const sessionStore = useSessionStore()
const logStore = useLogStore()
const settingsStore = useSettingsStore()

// 接收预览面板的 ref 和 cleanReasoning
const props = defineProps({
  previewPanelRef: Object,
  cleanReasoning: {
    type: Boolean,
    default: true
  }
})

onMounted(() => {
  settingsStore.loadSettings()
})

const patching = ref(false)
const restoring = ref(false)
const lastResult = ref(null)

const canPatch = computed(() => {
  const session = sessionStore.getSelectedSession()
  const preview = sessionStore.preview
  return sessionStore.selectedId && preview && (
    (preview.changes?.length || 0) > 0 ||
    (session?.refusal_count || 0) > 0 ||
    preview.reasoning_count > 0 ||
    preview.thinking_count > 0
  )
})

const hasRefusalOnly = computed(() => {
  const session = sessionStore.getSelectedSession()
  return (sessionStore.preview?.changes?.length || 0) > 0 || (session?.refusal_count || 0) > 0
})

const hasThinkingOnly = computed(() => {
  const preview = sessionStore.preview
  return !hasRefusalOnly.value && ((preview?.thinking_count || 0) > 0 || (preview?.reasoning_count || 0) > 0)
})

const cleanButtonLabel = computed(() => {
  if (sessionStore.aiRewriteLoading && hasRefusalOnly.value) return t('action.aiRewriteRunning')
  if (hasRefusalOnly.value && settingsStore.aiEnabled) {
    return sessionStore.aiRewrite ? t('action.cleanWithAiRewrite') : t('action.cleanAutoRewriteFallback')
  }
  return hasRefusalOnly.value ? t('action.clean') : hasThinkingOnly.value ? t('preview.cleanThinking') : t('preview.cleanReasoning')
})

// 设置预览面板引用（由父组件调用）
function setPreviewPanelRef(ref) {
  previewPanelRefInternal.value = ref
}

const previewPanelRefInternal = ref(null)

async function handlePatch() {
  if (!canPatch.value) return

  const preview = sessionStore.preview
  const session = sessionStore.getSelectedSession()
  const changesCount = preview?.changes?.length || 0
  const reasoningCount = preview?.reasoning_count || 0
  const thinkingCount = preview?.thinking_count || 0

  // 获取选中的行号
  let selectedLines = null
  const panelRef = props.previewPanelRef || previewPanelRefInternal.value
  if (panelRef && changesCount > 1) {
    const selected = panelRef.getSelectedLines()
    if (selected.length > 0 && selected.length < changesCount) {
      selectedLines = selected
    }
  }

  const selectedInfo = selectedLines ? ` (${selectedLines.length}/${changesCount})` : ''

  // 根据内容类型显示不同的确认对话框
  if (!hasRefusalOnly.value && (reasoningCount > 0 || thinkingCount > 0)) {
    // 无拒绝内容，只有推理/thinking 内容
    const details = []
    if (reasoningCount > 0) details.push(`${reasoningCount} ${t('preview.reasoningBlocks')}`)
    if (thinkingCount > 0) details.push(`${thinkingCount} Thinking Block`)
    dialog.info({
      title: t('action.confirmClean'),
      content: `${t('action.confirmCleanMessage')}\n\n${details.join('、')}`,
      positiveText: t('common.confirm'),
      negativeText: t('common.cancel'),
      onPositiveClick: () => {
        executePatch(selectedLines)
      }
    })
  } else {
    // 有拒绝内容
    dialog.warning({
      title: t('action.confirmClean'),
      content: `${confirmCleanContent.value}${selectedInfo}`,
      positiveText: t('common.confirm'),
      negativeText: t('common.cancel'),
      onPositiveClick: () => {
        executePatch(selectedLines)
      }
    })
  }
}

async function executePatch(selectedLines = null) {
  patching.value = true
  lastResult.value = null
  logStore.addLog(t('action.cleaning'), 'info')

  try {
    const result = await sessionStore.patchSession(null, selectedLines, props.cleanReasoning)

    if (result.success) {
      message.success(result.message)
      lastResult.value = { type: 'success', message: result.message }
      logStore.addLog(result.message, 'success')

      if (result.backup_path) {
        logStore.addLog(`${t('action.backupCreated')}: ${result.backup_path}`, 'info')
      }
    } else {
      message.error(result.message)
      lastResult.value = { type: 'error', message: result.message }
      logStore.addLog(result.message, 'error')
    }
  } catch (error) {
    message.error(error.message)
    lastResult.value = { type: 'error', message: error.message }
    logStore.addLog(error.message, 'error')
  } finally {
    patching.value = false
  }
}

const canRestore = computed(() => {
  const s = sessionStore.getSelectedSession()
  return sessionStore.selectedId && s?.has_backup
})

const canAIRewrite = computed(() => {
  return sessionStore.selectedId
    && (sessionStore.preview?.changes?.length || 0) > 0
    && settingsStore.aiEnabled
    && !sessionStore.aiRewriteLoading
})

const confirmCleanContent = computed(() => {
  if (hasRefusalOnly.value && sessionStore.aiRewrite?.items?.length > 0) {
    return t('action.confirmCleanWithAiMessage', { count: sessionStore.aiRewrite.items.length })
  }
  if (hasRefusalOnly.value && settingsStore.aiEnabled && !sessionStore.aiRewriteLoading) {
    return t('action.confirmCleanDefaultBecauseAiMissing')
  }
  return t('action.confirmCleanMessage')
})

async function handleRestore() {
  if (!sessionStore.selectedId) return

  restoring.value = true
  try {
    const backups = await sessionStore.listBackups()
    if (!backups || backups.length === 0) {
      message.warning(t('action.noBackup'))
      return
    }

    // 构建备份选项列表
    const backupOptions = backups.map((b, i) => ({
      label: `${b.timestamp}  (${formatBackupSize(b.size)})`,
      value: b.filename
    }))

    selectedBackup = backupOptions[0].value
    dialog.warning({
      title: t('action.selectBackup'),
      content: () => {
        return h('div', {}, [
          h('p', { style: 'margin-bottom: 12px; color: #999;' }, `${t('action.selectBackup')} (${backups.length})`),
          h(NSelect, {
            options: backupOptions,
            defaultValue: backupOptions[0].value,
            onUpdateValue: (v) => { selectedBackup = v }
          })
        ])
      },
      positiveText: t('action.confirmRestore'),
      negativeText: t('common.cancel'),
      onPositiveClick: async () => {
        const filename = selectedBackup || backupOptions[0].value
        logStore.addLog(`Restoring: ${filename}`, 'info')
        try {
          const result = await sessionStore.restoreSession(null, filename)
          if (result.success) {
            message.success(result.message)
            lastResult.value = { type: 'success', message: result.message }
            logStore.addLog(result.message, 'success')
          } else {
            message.error(result.message)
            logStore.addLog(result.message, 'error')
          }
        } catch (e) {
          message.error(e.message)
          logStore.addLog(e.message, 'error')
        }
      }
    })
  } catch (error) {
    message.error(error.message)
    logStore.addLog(error.message, 'error')
  } finally {
    restoring.value = false
  }
}

let selectedBackup = null

function formatBackupSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function handleAIAnalyze() {
  if (!canAIRewrite.value) return
  logStore.addLog(t('enhance.rewriteLoading'), 'info')
  try {
    const result = await sessionStore.requestAIRewrite()
    if (result.success) {
      const itemCount = result.items?.length || 0
      message.success(`${t('enhance.aiGenerated')} ${itemCount}`)
      logStore.addLog(`AI rewrite: ${itemCount} items`, 'success')
    } else {
      message.error(result.error || t('error.rewriteFailed'))
      logStore.addLog(result.error || t('error.rewriteFailed'), 'error')
    }
  } catch (error) {
    message.error(error.message)
    logStore.addLog(error.message, 'error')
  }
}
</script>

<style scoped>
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid #3a3a3a;
}

.left-actions {
  display: flex;
  gap: 12px;
}

.right-info {
  display: flex;
  align-items: center;
}
</style>
