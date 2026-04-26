<template>
  <div class="prompt-enhance-panel">
    <n-space vertical size="large">
      <!-- CTF/渗透模式（Tab 布局） -->
      <n-card :title="$t('enhance.ctfMode')" size="small">
        <n-tabs type="line" animated>

          <!-- ── Codex ── -->
          <n-tab-pane name="codex" display-directive="show">
            <template #tab>
              <span class="tab-label">
                <span class="status-dot" :class="{
                  'dot-success': ctfStore.status?.installed || ctfStore.status?.global_installed,
                  'dot-warning': !ctfStore.status?.installed && ctfStore.status?.global_installed,
                }"></span>
                Codex
              </span>
            </template>

            <n-space vertical size="large" style="padding-top: 4px">
              <!-- 提示词模板（最上面：先选模板再看启用） -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.editPromptShared') }}</n-text>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfTemplateDesc') }}</n-text>
                <n-spin :show="ctfStore.prompts.codex.loading" style="margin-top: 8px">
                  <div class="template-row">
                    <n-select v-model:value="codexSelectedTemplate" size="small" :placeholder="ctfStore.templates.codex.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectTemplate')" :options="templateOptions('codex')" :disabled="ctfStore.templates.codex.length === 0" :render-label="(option) => renderTemplateLabel(option, 'codex')" clearable style="flex: 1" @update:value="(v) => { if (v) applyTemplate('codex', v) }" />
                    <n-button size="small" :disabled="ctfStore.templates.codex.length >= MAX_TEMPLATES" @click="openSaveTemplate('codex')">+ {{ $t('enhance.saveAsTemplate') }}</n-button>
                  </div>
                  <n-input v-model:value="codexPromptText" type="textarea" :rows="8" style="font-family: monospace; font-size: 12px" />
                  <n-space style="margin-top: 8px" align="center">
                    <n-button size="small" :disabled="ctfStore.prompts.codex.is_default" @click="handleResetPrompt('codex')">{{ $t('enhance.restoreDefault') }}</n-button>
                    <n-button size="small" type="primary" @click="handleSavePrompt('codex', codexPromptText)">{{ $t('common.save') }}</n-button>
                  </n-space>
                </n-spin>
              </div>

              <n-divider style="margin: 4px 0" />

              <!-- Profile 模式 -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>Profile {{ $t('enhance.ctfMode') }}</n-text>
                  <n-tag :type="ctfStore.status?.installed ? 'success' : 'default'" size="small" :bordered="false">
                    {{ ctfStore.status?.installed ? $t('common.enabled') : $t('common.disabled') }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfProfileDesc') }}</n-text>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.installed" type="primary" size="small" :loading="ctfStore.installLoading" @click="handleInstall">{{ $t('enhance.enable') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.installLoading" @click="handleUninstall">{{ $t('enhance.disable') }}</n-button>
                </div>
                <p v-if="ctfStore.status?.installed" class="command-inline-hint">
                  {{ $t('enhance.ctfProfileCmdPre') }}<code>codex -p ctf</code>{{ $t('enhance.ctfProfileCmdPost') }}
                </p>
              </div>

              <n-divider style="margin: 4px 0" />

              <!-- 全局模式 -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.ctfGlobalMode') }}</n-text>
                  <n-tag :type="ctfStore.status?.global_installed ? 'warning' : 'default'" size="small" :bordered="false">
                    {{ ctfStore.status?.global_installed ? $t('common.enabled') : $t('common.disabled') }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfGlobalDesc') }}</n-text>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.global_installed" type="primary" size="small" :loading="ctfStore.globalInstallLoading" @click="handleInstallGlobal">{{ $t('enhance.enableGlobal') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.globalInstallLoading" @click="handleUninstallGlobal">{{ $t('enhance.disableGlobal') }}</n-button>
                </div>
                <n-alert v-if="ctfStore.status?.global_installed" type="warning" :bordered="false" style="margin-top: 8px">{{ $t('enhance.ctfGlobalWarning') }}</n-alert>
              </div>
            </n-space>
          </n-tab-pane>

          <!-- ── Claude Code ── -->
          <n-tab-pane v-if="settingsStore.claudeCodeEnabled" name="claude_code" display-directive="show">
            <template #tab>
              <span class="tab-label">
                <span class="status-dot" :class="{ 'dot-success': ctfStore.status?.claude_installed }"></span>
                Claude Code
              </span>
            </template>

            <n-space vertical size="large" style="padding-top: 4px">
              <!-- 提示词模板（最上面：先选模板再看启用） -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.editPromptShared') }}</n-text>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfTemplateDesc') }}</n-text>
                <n-spin :show="ctfStore.prompts.claude_code.loading" style="margin-top: 8px">
                  <div class="template-row">
                    <n-select v-model:value="claudeSelectedTemplate" size="small" :placeholder="ctfStore.templates.claude_code.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectTemplate')" :options="templateOptions('claude_code')" :disabled="ctfStore.templates.claude_code.length === 0" :render-label="(option) => renderTemplateLabel(option, 'claude_code')" clearable style="flex: 1" @update:value="(v) => { if (v) applyTemplate('claude_code', v) }" />
                    <n-button size="small" :disabled="ctfStore.templates.claude_code.length >= MAX_TEMPLATES" @click="openSaveTemplate('claude_code')">+ {{ $t('enhance.saveAsTemplate') }}</n-button>
                  </div>
                  <n-input v-model:value="claudePromptText" type="textarea" :rows="8" style="font-family: monospace; font-size: 12px" />
                  <n-space style="margin-top: 8px" align="center">
                    <n-button size="small" :disabled="ctfStore.prompts.claude_code.is_default" @click="handleResetPrompt('claude_code')">{{ $t('enhance.restoreDefault') }}</n-button>
                    <n-button size="small" type="primary" @click="handleSavePrompt('claude_code', claudePromptText)">{{ $t('common.save') }}</n-button>
                  </n-space>
                </n-spin>
              </div>

              <n-divider style="margin: 4px 0" />

              <!-- CTF/渗透模式启用 -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.ctfMode') }}</n-text>
                  <n-tag :type="ctfStore.status?.claude_installed ? 'success' : 'default'" size="small" :bordered="false">
                    {{ ctfStore.status?.claude_installed ? $t('common.enabled') : $t('common.disabled') }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.claudeDesc') }}</n-text>
                <n-alert type="warning" :bordered="false" style="margin-top: 4px">{{ $t('enhance.claudeWarning') }}</n-alert>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.claude_installed" type="primary" size="small" :loading="ctfStore.claudeInstallLoading" @click="handleClaudeInstall">{{ $t('enhance.enable') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.claudeInstallLoading" @click="handleClaudeUninstall">{{ $t('enhance.disable') }}</n-button>
                </div>
                <p v-if="ctfStore.status?.claude_installed" class="command-inline-hint">
                  {{ $t('enhance.activationCommand') }}：<code>cd ~/.claude-ctf-workspace && claude</code>
                </p>
              </div>
            </n-space>
          </n-tab-pane>

          <!-- ── OpenCode ── -->
          <n-tab-pane v-if="settingsStore.opencodeEnabled" name="opencode" display-directive="show">
            <template #tab>
              <span class="tab-label">
                <span class="status-dot" :class="{ 'dot-success': ctfStore.status?.opencode_installed }"></span>
                OpenCode
              </span>
            </template>

            <n-space vertical size="large" style="padding-top: 4px">
              <!-- 提示词模板（最上面：先选模板再看启用） -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.editPromptShared') }}</n-text>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfTemplateDesc') }}</n-text>
                <n-spin :show="ctfStore.prompts.opencode.loading" style="margin-top: 8px">
                  <div class="template-row">
                    <n-select v-model:value="opencodeSelectedTemplate" size="small" :placeholder="ctfStore.templates.opencode.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectTemplate')" :options="templateOptions('opencode')" :disabled="ctfStore.templates.opencode.length === 0" :render-label="(option) => renderTemplateLabel(option, 'opencode')" clearable style="flex: 1" @update:value="(v) => { if (v) applyTemplate('opencode', v) }" />
                    <n-button size="small" :disabled="ctfStore.templates.opencode.length >= MAX_TEMPLATES" @click="openSaveTemplate('opencode')">+ {{ $t('enhance.saveAsTemplate') }}</n-button>
                  </div>
                  <n-input v-model:value="opencodePromptText" type="textarea" :rows="8" style="font-family: monospace; font-size: 12px" />
                  <n-space style="margin-top: 8px" align="center">
                    <n-button size="small" :disabled="ctfStore.prompts.opencode.is_default" @click="handleResetPrompt('opencode')">{{ $t('enhance.restoreDefault') }}</n-button>
                    <n-button size="small" type="primary" @click="handleSavePrompt('opencode', opencodePromptText)">{{ $t('common.save') }}</n-button>
                  </n-space>
                </n-spin>
              </div>

              <n-divider style="margin: 4px 0" />

              <!-- CTF/渗透模式启用 -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.ctfMode') }}</n-text>
                  <n-tag :type="ctfStore.status?.opencode_installed ? 'success' : 'default'" size="small" :bordered="false">
                    {{ ctfStore.status?.opencode_installed ? $t('common.enabled') : $t('common.disabled') }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.opencodeDesc') }}</n-text>
                <n-alert type="warning" :bordered="false" style="margin-top: 4px">{{ $t('enhance.opencodeWarning') }}</n-alert>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.opencode_installed" type="primary" size="small" :loading="ctfStore.opencodeInstallLoading" @click="handleOpencodeInstall">{{ $t('enhance.enable') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.opencodeInstallLoading" @click="handleOpencodeUninstall">{{ $t('enhance.disable') }}</n-button>
                </div>
                <p v-if="ctfStore.status?.opencode_installed" class="command-inline-hint">
                  {{ $t('enhance.activationCommand') }}：<code>cd ~/.opencode-ctf-workspace && opencode</code>
                </p>
              </div>
            </n-space>
          </n-tab-pane>

        </n-tabs>
      </n-card>

      <!-- 提示词改写器（仅 CTF 启用时显示） -->
      <n-card v-if="anyCtfEnabled" :title="$t('enhance.promptRewrite')" size="small">
        <n-space vertical>
          <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.promptRewriteDesc') }}</n-text>

          <n-form-item :label="$t('enhance.originalPrompt')">
            <n-input
              v-model:value="rewriteInput" type="textarea" :rows="3"
              :placeholder="$t('enhance.originalPromptPlaceholder')"
            />
          </n-form-item>

          <n-space align="center">
            <n-button
              type="primary"
              :disabled="!rewriteInput.trim() || !settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
              :loading="ctfStore.rewriteLoading" @click="handleRewrite"
            >{{ $t('enhance.aiRewriteBtn') }}</n-button>
            <n-alert
              v-if="!settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
              type="warning" :bordered="false" style="padding: 4px 10px"
            >{{ $t('enhance.noAiConfig') }}</n-alert>
          </n-space>

          <div id="rewrite-result">
            <n-card v-if="ctfStore.rewrittenRequest" size="small" style="margin-top: 4px">
              <template #header>
                <n-space align="center">
                  <span>{{ $t('enhance.rewrittenPrompt') }}</span>
                  <n-tag size="small" type="info">{{ ctfStore.rewriteStrategy }}</n-tag>
                </n-space>
              </template>
              <n-input :value="ctfStore.rewrittenRequest" type="textarea" :rows="4" readonly />
              <template #action>
                <n-space>
                  <n-button size="small" type="primary" @click="copyRewritten">{{ $t('enhance.copyResult') }}</n-button>
                  <n-button size="small" @click="clearRewrite">{{ $t('common.clear') }}</n-button>
                </n-space>
              </template>
            </n-card>
          </div>

          <n-alert v-if="ctfStore.rewriteError" type="error" :bordered="false">
            {{ ctfStore.rewriteError }}
          </n-alert>
        </n-space>
      </n-card>

      <!-- 推荐工作流 -->
      <n-card :title="$t('help.workflow')" size="small">
        <n-tabs type="segment" size="small">
          <n-tab-pane name="codex" tab="Codex">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.ctfProfileDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="Profile: codex -p ctf; Global: codex" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.promptRewriteDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
          <n-tab-pane name="claude" tab="Claude Code">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.claudeDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="cd ~/.claude-ctf-workspace && claude" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.promptRewriteDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
          <n-tab-pane name="opencode" tab="OpenCode">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.opencodeDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="cd ~/.opencode-ctf-workspace && opencode" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.promptRewriteDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </n-space>

    <!-- 保存模板对话框 -->
    <n-modal
      v-model:show="saveTemplateModal.show"
      preset="dialog"
      :title="$t('enhance.saveAsTemplate')"
      :positive-text="$t('common.confirm')"
      :negative-text="$t('common.cancel')"
      @positive-click="confirmSaveTemplate"
    >
      <n-input
        v-model:value="saveTemplateModal.name"
        :placeholder="$t('enhance.templateNameHint')"
        :maxlength="20"
        show-count
        @keydown.enter="confirmSaveTemplate"
        style="margin-top: 8px"
      />
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage, useDialog, NButton } from 'naive-ui'
import { useCTFStore } from '../stores/ctfStore'
import { useSettingsStore } from '../stores/settingsStore'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const ctfStore = useCTFStore()
const settingsStore = useSettingsStore()

// 任意 CTF 模式已启用时才显示改写功能
const anyCtfEnabled = computed(() =>
  ctfStore.status?.installed ||
  ctfStore.status?.global_installed ||
  ctfStore.status?.claude_installed ||
  ctfStore.status?.opencode_installed
)

const MAX_TEMPLATES = 5

const rewriteInput = ref('')
const codexPromptText = ref('')
const codexSelectedTemplate = ref(null)
const claudePromptText = ref('')
const claudeSelectedTemplate = ref(null)
const opencodePromptText = ref('')
const opencodeSelectedTemplate = ref(null)
// 保存模板对话框状态
const saveTemplateModal = ref({ show: false, tool: '', name: '' })

onMounted(async () => {
  await Promise.all([
    ctfStore.fetchStatus(),
    ctfStore.fetchPrompt('codex'),
    ctfStore.fetchPrompt('claude_code'),
    ctfStore.fetchPrompt('opencode'),
    ctfStore.fetchTemplates('codex'),
    ctfStore.fetchTemplates('claude_code'),
    ctfStore.fetchTemplates('opencode'),
  ])
  codexPromptText.value = ctfStore.prompts.codex.prompt
  claudePromptText.value = ctfStore.prompts.claude_code.prompt
  opencodePromptText.value = ctfStore.prompts.opencode.prompt

  // 用 is_default 判断是否匹配默认模板，选中对应模板名
  for (const tool of ['codex', 'claude_code', 'opencode']) {
    if (ctfStore.prompts[tool].is_default) {
      const defaultTpl = ctfStore.templates[tool].find(t => t.default === true)
      if (defaultTpl) getSelectedTemplateRef(tool).value = defaultTpl.name
    }
  }
})

// ─── 模板相关 ──────────────────────────────────────────

function templateOptions(tool) {
  return ctfStore.templates[tool].map(tpl => ({
    label: tpl.name,
    value: tpl.name,
    builtin: tpl.builtin || false,
  }))
}

function renderTemplateLabel(option, tool) {
  const isBuiltin = option.builtin === true
  const children = [
    h('span', {
      style: 'flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap',
    }, option.label),
  ]
  if (!isBuiltin) {
    children.push(h(NButton, {
      text: true,
      size: 'tiny',
      type: 'error',
      focusable: false,
      style: 'flex-shrink:0; padding: 0 4px',
      onClick: (e) => {
        e.stopPropagation()
        confirmDeleteTemplate(tool, option.value)
      },
    }, { default: () => '✕' }))
  }
  return h('div', {
    style: 'display:flex; align-items:center; justify-content:space-between; width:100%; gap:8px',
  }, children)
}

async function applyTemplate(tool, templateName) {
  getSelectedTemplateRef(tool).value = templateName
  const prompt = await ctfStore.fetchTemplatePrompt(tool, templateName)
  if (prompt) {
    getPromptTextRef(tool).value = prompt
  }
}

function openSaveTemplate(tool) {
  const text = getPromptTextRef(tool).value
  if (!text?.trim()) {
    message.warning(t('enhance.promptEmpty'))
    return
  }
  saveTemplateModal.value = { show: true, tool, name: '' }
}

async function confirmSaveTemplate() {
  const name = saveTemplateModal.value.name.trim()
  if (!name) return false  // 阻止对话框关闭
  const tool = saveTemplateModal.value.tool
  const prompt = getPromptTextRef(tool).value
  const result = await ctfStore.saveTemplate(tool, name, prompt)
  if (result.success) {
    message.success(t('enhance.templateSaved'))
    saveTemplateModal.value.show = false
  } else {
    message.error(result.message)
    return false
  }
}

function confirmDeleteTemplate(tool, name) {
  dialog.warning({
    title: t('common.confirm'),
    content: `删除模板「${name}」？`,
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.deleteTemplate(tool, name)
      if (result.success) {
        message.success(t('enhance.templateDeleted'))
      } else {
        message.error(result.message)
      }
    },
  })
}

// ─── 提示词管理 ──────────────────────────────────────────

function getPromptTextRef(tool) {
  if (tool === 'codex') return codexPromptText
  if (tool === 'claude_code') return claudePromptText
  return opencodePromptText
}

function getSelectedTemplateRef(tool) {
  if (tool === 'codex') return codexSelectedTemplate
  if (tool === 'claude_code') return claudeSelectedTemplate
  return opencodeSelectedTemplate
}

async function handleSavePrompt(tool, text) {
  const result = await ctfStore.savePrompt(tool, text)
  if (result.success) {
    message.success(t('enhance.promptSaved'))
  } else {
    message.error(result.message || t('enhance.promptSaveError'))
  }
}

async function handleResetPrompt(tool) {
  const result = await ctfStore.resetPromptToDefault(tool)
  if (result.success) {
    getPromptTextRef(tool).value = ctfStore.prompts[tool].prompt
    message.success(t('enhance.promptRestored'))
  }
}

// ─── CTF 安装/卸载 ──────────────────────────────────────

async function handleInstall() {
  const result = await ctfStore.install()
  message[result.success ? 'success' : 'error'](result.message)
}

async function handleUninstall() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableCtf'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstall()
      message[result.success ? 'success' : 'error'](result.message)
    }
  })
}

async function handleInstallGlobal() {
  const result = await ctfStore.installGlobal()
  message[result.success ? 'success' : 'error'](result.message)
}

async function handleUninstallGlobal() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableGlobal'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstallGlobal()
      message[result.success ? 'success' : 'error'](result.message)
    }
  })
}

async function handleClaudeInstall() {
  const result = await ctfStore.installClaude()
  message[result.success ? 'success' : 'error'](result.message)
}

async function handleClaudeUninstall() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableClaude'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstallClaude()
      message[result.success ? 'success' : 'error'](result.message)
    }
  })
}

async function handleOpencodeInstall() {
  const result = await ctfStore.installOpencode()
  message[result.success ? 'success' : 'error'](result.message)
}

async function handleOpencodeUninstall() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableOpencode'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstallOpencode()
      message[result.success ? 'success' : 'error'](result.message)
    }
  })
}

// ─── 提示词改写 ──────────────────────────────────────────

async function handleRewrite() {
  if (!rewriteInput.value.trim()) return
  const result = await ctfStore.rewritePrompt(rewriteInput.value)
  if (result.success) {
    message.success(t('enhance.rewriteSuccess'))
    nextTick(() => {
      document.getElementById('rewrite-result')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }
}

async function copyRewritten() {
  try {
    await navigator.clipboard.writeText(ctfStore.rewrittenRequest)
    message.success(t('common.copied'))
  } catch {
    message.error(t('common.error'))
  }
}

function clearRewrite() {
  rewriteInput.value = ''
  ctfStore.resetRewrite()
}
</script>

<style scoped>
.prompt-enhance-panel {
  max-width: 800px;
  margin: 0 auto;
}

code {
  background: rgba(128, 128, 128, 0.15);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}

.mode-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mode-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.command-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.command-inline-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--n-text-color-3);
  line-height: 1.6;
}

.template-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 5px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--n-text-color-disabled, #ccc);
}

.status-dot.dot-success {
  background: #18a058;
}

.status-dot.dot-warning {
  background: #f0a020;
}
</style>
