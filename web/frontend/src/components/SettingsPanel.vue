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
            <n-form-item :label="$t('settings.providerPreset')">
              <n-space vertical style="width: 100%">
                <n-select
                  v-model:value="selectedProviderKey"
                  :options="providerOptions"
                  :placeholder="$t('settings.providerPresetPlaceholder')"
                  clearable
                />
                <n-space v-if="selectedProvider" :wrap="false">
                  <n-select
                    v-model:value="selectedProviderRegion"
                    :options="regionOptions"
                    style="min-width: 140px"
                  />
                  <n-select
                    v-model:value="selectedProviderModel"
                    :options="modelOptions"
                    style="min-width: 180px"
                  />
                  <n-button secondary type="primary" @click="applyProviderPreset">
                    {{ $t('settings.applyProviderPreset') }}
                  </n-button>
                </n-space>
                <span class="form-hint">{{ $t('settings.providerPresetHint') }}</span>
              </n-space>
            </n-form-item>

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
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { useSettingsStore } from '../stores/settingsStore'
import { AI_PROVIDER_PRESETS, getProviderPreset } from '../constants/aiProviders'

const { t } = useI18n()
const message = useMessage()
const settingsStore = useSettingsStore()

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
const providerOptions = AI_PROVIDER_PRESETS.map((provider) => ({
  label: provider.label,
  value: provider.key
}))
const selectedProviderKey = ref(null)
const selectedProviderRegion = ref(null)
const selectedProviderModel = ref(null)
const selectedProvider = computed(() => getProviderPreset(selectedProviderKey.value))
const regionOptions = computed(() => {
  if (!selectedProvider.value) return []
  return selectedProvider.value.regions.map((region) => ({
    label: region.label,
    value: region.value
  }))
})
const modelOptions = computed(() => {
  if (!selectedProvider.value) return []
  return selectedProvider.value.models.map((model) => ({
    label: model.label,
    value: model.value
  }))
})

watch(selectedProvider, (provider) => {
  selectedProviderRegion.value = provider?.defaultRegion || null
  selectedProviderModel.value = provider?.defaultModel || null
})

function handleKeywordsChange(lang, value) {
  settingsStore.customKeywords[lang] = value
  settingsStore.markChanged()
}

function applyProviderPreset() {
  const provider = selectedProvider.value
  if (!provider) return

  const region = provider.regions.find((item) => item.value === selectedProviderRegion.value)
  const model = provider.models.find((item) => item.value === selectedProviderModel.value)
  if (!region || !model) return

  settingsStore.aiEndpoint = region.openaiBaseUrl
  settingsStore.aiModel = model.value
  settingsStore.markChanged()
}

async function handleSave() {
  try {
    await settingsStore.saveSettings()
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
