<template>
  <div class="prompt-enhance-panel">
    <n-space vertical size="large">
      <!-- CTF/渗透模式 — Codex -->
      <n-card title="CTF/渗透模式 — Codex" size="small">
        <template #header-extra>
          <n-tag :type="ctfStore.status?.installed ? 'success' : 'default'" size="small">
            {{ ctfStore.status?.installed ? '已启用' : '未启用' }}
          </n-tag>
        </template>

        <n-space vertical>
          <n-alert type="info" :bordered="false">
            <template #header>功能说明</template>
            注入安全测试上下文，降低请求被拒绝的概率。使用命令：<code>codex -p ctf</code>
          </n-alert>

          <n-alert type="warning" :bordered="false">
            修改后需要新开 Codex 会话才能生效
          </n-alert>

          <n-space>
            <n-button
              v-if="!ctfStore.status?.installed"
              type="primary"
              :loading="ctfStore.installLoading"
              @click="handleInstall"
            >
              启用
            </n-button>
            <n-button
              v-else
              type="warning"
              :loading="ctfStore.installLoading"
              @click="handleUninstall"
            >
              禁用
            </n-button>
          </n-space>
        </n-space>
      </n-card>

      <!-- CTF/渗透模式 — Claude Code -->
      <n-card title="CTF/渗透模式 — Claude Code" size="small">
        <template #header-extra>
          <n-tag :type="ctfStore.status?.claude_installed ? 'success' : 'default'" size="small">
            {{ ctfStore.status?.claude_installed ? '已启用' : '未启用' }}
          </n-tag>
        </template>

        <n-space vertical>
          <n-alert type="info" :bordered="false">
            <template #header>功能说明</template>
            创建 CTF 工作空间，通过项目级 CLAUDE.md 注入安全测试上下文。
          </n-alert>

          <n-alert type="info" :bordered="false">
            <template #header>激活命令</template>
            <code>cd ~/.claude-ctf-workspace && claude</code>
          </n-alert>

          <n-alert type="warning" :bordered="false">
            需要从 CTF 工作空间目录启动 Claude Code 才能生效
          </n-alert>

          <n-space>
            <n-button
              v-if="!ctfStore.status?.claude_installed"
              type="primary"
              :loading="ctfStore.claudeInstallLoading"
              @click="handleClaudeInstall"
            >
              启用
            </n-button>
            <n-button
              v-else
              type="warning"
              :loading="ctfStore.claudeInstallLoading"
              @click="handleClaudeUninstall"
            >
              禁用
            </n-button>
          </n-space>
        </n-space>
      </n-card>

      <!-- 提示词改写器 -->
      <n-card title="提示词改写器" size="small">
        <n-space vertical>
          <n-alert type="info" :bordered="false">
            将可能被拒绝的请求改写为更易接受的形式，需要配置 AI API
          </n-alert>

          <!-- 目标选择 -->
          <n-form-item label="目标平台">
            <n-segmented
              v-model:value="ctfStore.rewriteTarget"
              :options="targetOptions"
              size="small"
            />
          </n-form-item>

          <n-form-item label="原始请求">
            <n-input
              v-model:value="rewriteInput"
              type="textarea"
              :rows="3"
              placeholder="输入可能被拒绝的请求..."
            />
          </n-form-item>

          <n-button
            :disabled="!rewriteInput.trim() || !settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
            :loading="ctfStore.rewriteLoading"
            @click="handleRewrite"
          >
            改写
          </n-button>

          <n-alert
            v-if="!settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
            type="warning"
            :bordered="false"
          >
            请先在「设置」中配置 AI API
          </n-alert>

          <n-collapse-transition :show="ctfStore.rewrittenRequest">
            <n-card size="small" style="margin-top: 12px">
              <template #header>
                <n-space align="center">
                  <span>改写结果</span>
                  <n-tag size="small" type="info">{{ ctfStore.rewriteStrategy }}</n-tag>
                </n-space>
              </template>
              <n-input
                :value="ctfStore.rewrittenRequest"
                type="textarea"
                :rows="4"
                readonly
              />
              <template #action>
                <n-space>
                  <n-button size="small" @click="copyRewritten">复制</n-button>
                  <n-button size="small" @click="clearRewrite">清除</n-button>
                </n-space>
              </template>
            </n-card>
          </n-collapse-transition>

          <n-alert v-if="ctfStore.rewriteError" type="error" :bordered="false">
            {{ ctfStore.rewriteError }}
          </n-alert>
        </n-space>
      </n-card>

      <!-- 推荐工作流 -->
      <n-card title="推荐工作流" size="small">
        <n-tabs type="segment" size="small">
          <n-tab-pane name="codex" tab="Codex">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step title="启用 CTF/渗透模式" description="注入安全测试上下文" />
              <n-step title="新开会话" description="使用 codex -p ctf 启动" />
              <n-step title="发送请求" description="如果被拒绝，使用提示词改写器" />
              <n-step title="继续对话" description="如果仍被拒绝，使用会话清理功能" />
            </n-steps>
          </n-tab-pane>
          <n-tab-pane name="claude" tab="Claude Code">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step title="启用 CTF/渗透模式" description="创建 CTF 工作空间" />
              <n-step title="进入工作空间" description="cd ~/.claude-ctf-workspace && claude" />
              <n-step title="发送请求" description="如果被拒绝，使用提示词改写器" />
              <n-step title="清理会话" description="如果仍被拒绝，使用会话清理功能" />
            </n-steps>
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { useCTFStore } from '../stores/ctfStore'
import { useSettingsStore } from '../stores/settingsStore'

const message = useMessage()
const dialog = useDialog()
const ctfStore = useCTFStore()
const settingsStore = useSettingsStore()

const rewriteInput = ref('')
const targetOptions = [
  { label: 'Codex', value: 'codex' },
  { label: 'Claude Code', value: 'claude_code' },
]

onMounted(() => {
  ctfStore.fetchStatus()
})

// Codex
async function handleInstall() {
  const result = await ctfStore.install()
  if (result.success) {
    message.success(result.message)
  } else {
    message.error(result.message)
  }
}

async function handleUninstall() {
  dialog.warning({
    title: '确认禁用',
    content: '确定要禁用 Codex CTF/渗透模式吗？',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      const result = await ctfStore.uninstall()
      if (result.success) {
        message.success(result.message)
      } else {
        message.error(result.message)
      }
    }
  })
}

// Claude Code
async function handleClaudeInstall() {
  const result = await ctfStore.installClaude()
  if (result.success) {
    message.success(result.message)
  } else {
    message.error(result.message)
  }
}

async function handleClaudeUninstall() {
  dialog.warning({
    title: '确认禁用',
    content: '确定要禁用 Claude Code CTF/渗透模式吗？将删除 CTF 工作空间中的 CLAUDE.md。',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      const result = await ctfStore.uninstallClaude()
      if (result.success) {
        message.success(result.message)
      } else {
        message.error(result.message)
      }
    }
  })
}

// 提示词改写
async function handleRewrite() {
  if (!rewriteInput.value.trim()) return
  const result = await ctfStore.rewritePrompt(rewriteInput.value)
  if (result.success) {
    message.success('改写完成')
  }
}

async function copyRewritten() {
  try {
    await navigator.clipboard.writeText(ctfStore.rewrittenRequest)
    message.success('已复制')
  } catch {
    message.error('复制失败')
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

.n-card {
  background: var(--color-bg-1);
}

code {
  background: #333;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
