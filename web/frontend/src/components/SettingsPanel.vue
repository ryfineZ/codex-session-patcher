<template>
  <div class="settings-panel">
    <n-space vertical size="large">
      <!-- AI 配置 -->
      <n-card :title="$t('settings.aiConfig')" size="small">
        <template #header-extra>
          <n-tag :type="settingsStore.aiEnabled ? 'success' : 'default'" size="small">
            {{ settingsStore.aiEnabled ? $t('common.enabled') : $t('common.disabled') }}
          </n-tag>
        </template>

        <n-space vertical>
          <n-form-item :label="$t('settings.aiEnabled')">
            <n-switch
              v-model:value="settingsStore.aiEnabled"
              @update:value="settingsStore.markChanged"
            />
          </n-form-item>

          <n-collapse-transition :show="settingsStore.aiEnabled">
            <n-form-item :label="$t('settings.apiEndpoint')">
              <n-input
                v-model:value="settingsStore.aiEndpoint"
                :placeholder="$t('settings.apiEndpointPlaceholder')"
                @update:value="settingsStore.markChanged"
              />
              <template #feedback>
                <span class="form-hint">{{ $t('settings.aiConfigDesc') }}</span>
              </template>
            </n-form-item>

            <n-form-item :label="$t('settings.apiKey')">
              <n-input
                v-model:value="settingsStore.aiKey"
                type="password"
                show-password-on="click"
                :placeholder="$t('settings.apiKeyPlaceholder')"
                @update:value="settingsStore.markChanged"
              />
            </n-form-item>

            <n-form-item :label="$t('settings.modelName')">
              <n-input
                v-model:value="settingsStore.aiModel"
                :placeholder="$t('settings.modelNamePlaceholder')"
                @update:value="settingsStore.markChanged"
              />
            </n-form-item>
          </n-collapse-transition>

          <n-alert type="info" :bordered="false">
            {{ $t('enhance.promptRewriteDesc') }}
          </n-alert>
        </n-space>
      </n-card>

      <!-- 平台支持 -->
      <n-card :title="$t('settings.platformSupport')" size="small">
        <n-space vertical>
          <n-form-item :label="$t('settings.claudeCodeEnabled')">
            <n-switch
              :value="settingsStore.claudeCodeEnabled"
              @update:value="settingsStore.setClaudeCodeEnabled"
            />
            <template #feedback>
              <span class="form-hint">{{ $t('settings.claudeCodeEnabledHint') }}</span>
            </template>
          </n-form-item>

          <n-form-item :label="$t('settings.claudeProjectDirs')">
            <n-input
              v-model:value="claudeProjectDirsText"
              type="textarea"
              :rows="4"
              :placeholder="$t('settings.claudeProjectDirsPlaceholder')"
            />
            <template #feedback>
              <span class="form-hint">{{ $t('settings.claudeProjectDirsHint') }}</span>
            </template>
          </n-form-item>

          <n-form-item :label="$t('settings.opencodeEnabled')">
            <n-switch
              :value="settingsStore.opencodeEnabled"
              @update:value="settingsStore.setOpencodeEnabled"
            />
            <template #feedback>
              <span class="form-hint">{{ $t('settings.opencodeEnabledHint') }}</span>
            </template>
          </n-form-item>
        </n-space>
      </n-card>

      <!-- 会话清理配置 -->
      <n-card :title="$t('action.clean')" size="small">
        <n-space vertical>
          <n-form-item :label="$t('settings.showAllSessions')">
            <n-switch
              :value="settingsStore.showAllSessions"
              @update:value="settingsStore.setShowAllSessions"
            />
            <template #feedback>
              <span class="form-hint">{{ $t('settings.showAllSessionsHint') }}</span>
            </template>
          </n-form-item>

          <n-form-item :label="$t('settings.mockResponse')">
            <n-input
              v-model:value="settingsStore.mockResponse"
              type="textarea"
              :rows="3"
              :placeholder="$t('settings.mockResponsePlaceholder')"
              @update:value="settingsStore.markChanged"
            />
            <template #feedback>
              <span class="form-hint">{{ $t('settings.mockResponseDesc') }}</span>
            </template>
          </n-form-item>
        </n-space>
      </n-card>

      <!-- 拒绝检测 -->
      <n-card :title="$t('settings.refusalDetection')" size="small">
        <n-space vertical>
          <n-form-item :label="$t('settings.zhKeywords')">
            <div class="builtin-keywords">
              <n-tag v-for="kw in builtinZhKeywords" :key="kw" size="small" type="info" :bordered="false">{{ kw }}</n-tag>
            </div>
          </n-form-item>

          <n-form-item :label="$t('settings.enKeywords')">
            <div class="builtin-keywords">
              <n-tag v-for="kw in builtinEnKeywords" :key="kw" size="small" type="info" :bordered="false">{{ kw }}</n-tag>
            </div>
          </n-form-item>

          <n-form-item :label="$t('settings.customZhKeywords')">
            <n-dynamic-tags
              :value="zhKeywords"
              @update:value="handleKeywordsChange('zh', $event)"
            />
          </n-form-item>

          <n-form-item :label="$t('settings.customEnKeywords')">
            <n-dynamic-tags
              :value="enKeywords"
              @update:value="handleKeywordsChange('en', $event)"
            />
          </n-form-item>
        </n-space>
      </n-card>

      <!-- 保存按钮 -->
      <n-space justify="end">
        <n-button @click="handleReset">{{ $t('common.reset') }}</n-button>
        <n-button
          type="primary"
          :disabled="!settingsStore.changed"
          :loading="settingsStore.loading"
          @click="handleSave"
        >
          {{ $t('common.save') }}
        </n-button>
      </n-space>
    </n-space>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { useSettingsStore } from '../stores/settingsStore'
import { useSessionStore } from '../stores/sessionStore'

const { t } = useI18n()
const message = useMessage()
const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()

// 内置关键词
const builtinZhKeywords = [
  '抱歉', '无法', '违反', '不能', '拒绝', '不允许', '禁止',
  '很抱歉', '对不起', '不好意思', '我无法', '我不能'
]
const builtinEnKeywords = [
  'sorry', 'cannot', 'apologize', 'violate', 'policy',
  'as an AI', 'I cannot', "I'm unable", 'not able to',
  'against my', "I won't", 'refuse to', 'unable to',
  'I apologize', 'not permitted', 'not allowed'
]

// 自定义关键词
const zhKeywords = computed(() => settingsStore.customKeywords.zh || [])
const enKeywords = computed(() => settingsStore.customKeywords.en || [])
const claudeProjectDirsText = computed({
  get: () => (settingsStore.claudeProjectDirs || []).join('\n'),
  set: (value) => {
    settingsStore.claudeProjectDirs = [...new Set(
      value
        .split('\n')
        .map(item => item.trim())
        .filter(Boolean)
    )]
    settingsStore.markChanged()
  }
})

function handleKeywordsChange(lang, value) {
  settingsStore.customKeywords[lang] = value
  settingsStore.markChanged()
}

async function handleSave() {
  try {
    await settingsStore.saveSettings()
    await sessionStore.fetchSessions()
    message.success(t('common.success'))
  } catch (error) {
    message.error(t('common.error') + ': ' + error.message)
  }
}

function handleReset() {
  settingsStore.resetSettings()
  message.info(t('settings.resetSuccess'))
}
</script>

<style scoped>
.settings-panel {
  max-width: 800px;
  margin: 0 auto;
}

.n-card {
  background: var(--color-bg-1);
}

.form-hint {
  font-size: 11px;
  color: #666;
}

.builtin-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
