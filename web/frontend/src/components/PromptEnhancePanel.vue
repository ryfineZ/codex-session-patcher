<template>
  <div class="prompt-enhance-panel">
    <n-space vertical size="large">
      <!-- CTF/渗透模式（Tab 布局） -->
      <n-card :title="$t('enhance.ctfMode')" size="small">
        <div class="status-overview">
          <div class="status-title-row">
            <div>
              <n-text strong>{{ $t('enhance.currentMode') }}</n-text>
              <div class="status-subtitle">{{ codexModeSummary }}</div>
            </div>
            <n-tag :type="codexModeTagType" size="large" :bordered="false">
              {{ codexModeLabel }}
            </n-tag>
          </div>

          <n-alert :type="codexModeAlertType" :bordered="false" class="mode-alert">
            {{ codexModeAdvice }}
          </n-alert>

          <div class="status-command-row">
            <span>{{ $t('enhance.startCommand') }}</span>
            <code>{{ ctfStore.status?.codex_activation_command || 'codex-patcher --install-ctf-config' }}</code>
            <n-button size="tiny" quaternary @click="copyText(ctfStore.status?.codex_activation_command || 'codex-patcher --install-ctf-config')">
              {{ $t('common.copy') }}
            </n-button>
            <n-button
              v-if="ctfStore.status?.codex_profile_ready || ctfStore.status?.codex_global_active"
              size="tiny"
              type="primary"
              ghost
              :loading="ctfStore.launchLoading"
              @click="handleLaunchCodex"
            >
              在新终端启动
            </n-button>
          </div>
        </div>

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
                  <div class="template-current-row">
                    <n-tag type="success" size="small" :bordered="false">
                      {{ $t('enhance.currentTemplate') }}：{{ currentTemplateName('codex') }}
                    </n-tag>
                    <n-text depth="3" class="template-active-hint">{{ $t('enhance.templateApplyHint') }}</n-text>
                  </div>
                  <div class="template-row">
                    <n-select v-model:value="codexSelectedTemplate" size="small" :placeholder="ctfStore.templates.codex.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectAndApplyTemplate')" :options="templateOptions('codex')" :disabled="ctfStore.templates.codex.length === 0" :render-label="(option) => renderTemplateLabel(option, 'codex')" clearable style="flex: 1" :loading="ctfStore.templateApplyLoading" @update:value="(v) => { if (v) applyTemplate('codex', v) }" />
                    <n-button size="small" @click="openTemplateManager('codex')">{{ $t('enhance.manageTemplates') }}</n-button>
                  </div>
                  <n-alert type="info" :bordered="false" class="template-restart-alert">
                    {{ $t('enhance.templateRestartHint') }}
                  </n-alert>
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
                  <n-tag :type="ctfStore.status?.codex_profile_ready ? 'success' : (ctfStore.status?.codex_mode === 'profile_broken' ? 'warning' : 'default')" size="small" :bordered="false">
                    {{ ctfStore.status?.codex_profile_ready ? $t('enhance.configReady') : (ctfStore.status?.codex_mode === 'profile_broken' ? $t('enhance.configBroken') : $t('common.disabled')) }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfProfileDesc') }}</n-text>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.codex_profile_ready" type="primary" size="small" :loading="ctfStore.installLoading" @click="handleInstall">{{ $t('enhance.enable') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.installLoading" @click="handleUninstall">{{ $t('enhance.disable') }}</n-button>
                </div>
                <n-alert v-if="ctfStore.status?.codex_profile_ready" type="info" :bordered="false" style="margin-top: 8px">
                  {{ $t('enhance.profileReadyButManual') }} <code>codex -p ctf</code>
                </n-alert>
                <n-alert v-if="ctfStore.status?.codex_profile_ready" type="success" :bordered="false" style="margin-top: 8px">
                  {{ $t('enhance.profileSessionDetection') }}
                </n-alert>
                <div class="profile-session-box">
                  <div class="profile-session-head">
                    <n-text strong>{{ $t('enhance.profileSessionOverview') }}</n-text>
                    <div class="profile-session-actions">
                      <n-tag type="success" size="small" :bordered="false">
                        {{ $t('enhance.profileSessionActiveCount', { count: ctfActiveCount }) }}
                      </n-tag>
                      <n-tag size="small" :bordered="false">
                        {{ $t('enhance.profileSessionTotalCount', { count: codexSessionCount }) }}
                      </n-tag>
                      <n-button size="tiny" quaternary :loading="sessionStore.loading" @click="refreshSessions">
                        {{ $t('common.refresh') }}
                      </n-button>
                    </div>
                  </div>

                  <n-alert v-if="sessionStore.loading && codexSessionCount === 0" type="info" :bordered="false">
                    {{ $t('enhance.profileSessionLoading') }}
                  </n-alert>
                  <n-empty v-else-if="codexSessionCount === 0" :description="$t('enhance.profileSessionNone')" size="small" />
                  <div v-else class="profile-session-content">
                    <div class="profile-session-summary">
                      {{ $t('enhance.profileSessionSummary', { active: ctfActiveCount, inactive: ctfInactiveCount, total: codexSessionCount }) }}
                    </div>

                    <div v-if="visibleCtfActiveSessions.length > 0" class="profile-session-list">
                      <div v-for="session in visibleCtfActiveSessions" :key="session.id" class="profile-session-row">
                        <span class="profile-session-id" :title="session.id">{{ session.id }}</span>
                        <n-tag type="success" size="tiny" :bordered="false">{{ $t('session.ctfActive') }}</n-tag>
                        <span class="profile-session-meta" :title="session.project_path || session.mtime">
                          {{ formatSessionMeta(session) }}
                        </span>
                      </div>
                      <div v-if="ctfActiveMoreCount > 0" class="profile-session-more">
                        {{ $t('enhance.profileSessionMore', { count: ctfActiveMoreCount }) }}
                      </div>
                    </div>
                    <n-alert v-else type="warning" :bordered="false">
                      {{ $t('enhance.profileSessionNoActive') }}
                    </n-alert>

                    <div v-if="ctfInactiveCount > 0" class="profile-session-inactive">
                      {{ $t('enhance.profileSessionInactiveHint', { count: ctfInactiveCount }) }}
                    </div>
                  </div>
                </div>
              </div>

              <n-divider style="margin: 4px 0" />

              <!-- 全局模式 -->
              <div class="mode-section">
                <div class="mode-header">
                  <n-text strong>{{ $t('enhance.ctfGlobalMode') }}</n-text>
                  <n-tag :type="ctfStore.status?.codex_global_active ? 'success' : (ctfStore.status?.codex_mode === 'global_broken' ? 'warning' : 'default')" size="small" :bordered="false">
                    {{ ctfStore.status?.codex_global_active ? $t('enhance.autoActive') : (ctfStore.status?.codex_mode === 'global_broken' ? $t('enhance.configBroken') : $t('common.disabled')) }}
                  </n-tag>
                </div>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">{{ $t('enhance.ctfGlobalDesc') }}</n-text>
                <div style="margin-top: 8px">
                  <n-button v-if="!ctfStore.status?.codex_global_active" type="primary" size="small" :loading="ctfStore.globalInstallLoading" @click="handleInstallGlobal">{{ $t('enhance.enableGlobal') }}</n-button>
                  <n-button v-else type="warning" size="small" :loading="ctfStore.globalInstallLoading" @click="handleUninstallGlobal">{{ $t('enhance.disableGlobal') }}</n-button>
                </div>
                <n-alert v-if="ctfStore.status?.codex_global_active" type="warning" :bordered="false" style="margin-top: 8px">{{ $t('enhance.ctfGlobalWarning') }}</n-alert>
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
                  <div class="template-current-row">
                    <n-tag type="success" size="small" :bordered="false">
                      {{ $t('enhance.currentTemplate') }}：{{ currentTemplateName('claude_code') }}
                    </n-tag>
                    <n-text depth="3" class="template-active-hint">{{ $t('enhance.templateApplyHint') }}</n-text>
                  </div>
                  <div class="template-row">
                    <n-select v-model:value="claudeSelectedTemplate" size="small" :placeholder="ctfStore.templates.claude_code.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectAndApplyTemplate')" :options="templateOptions('claude_code')" :disabled="ctfStore.templates.claude_code.length === 0" :render-label="(option) => renderTemplateLabel(option, 'claude_code')" clearable style="flex: 1" :loading="ctfStore.templateApplyLoading" @update:value="(v) => { if (v) applyTemplate('claude_code', v) }" />
                    <n-button size="small" @click="openTemplateManager('claude_code')">{{ $t('enhance.manageTemplates') }}</n-button>
                  </div>
                  <n-alert type="info" :bordered="false" class="template-restart-alert">
                    {{ $t('enhance.templateRestartHint') }}
                  </n-alert>
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
                  <div class="template-current-row">
                    <n-tag type="success" size="small" :bordered="false">
                      {{ $t('enhance.currentTemplate') }}：{{ currentTemplateName('opencode') }}
                    </n-tag>
                    <n-text depth="3" class="template-active-hint">{{ $t('enhance.templateApplyHint') }}</n-text>
                  </div>
                  <div class="template-row">
                    <n-select v-model:value="opencodeSelectedTemplate" size="small" :placeholder="ctfStore.templates.opencode.length === 0 ? $t('enhance.noTemplates') : $t('enhance.selectAndApplyTemplate')" :options="templateOptions('opencode')" :disabled="ctfStore.templates.opencode.length === 0" :render-label="(option) => renderTemplateLabel(option, 'opencode')" clearable style="flex: 1" :loading="ctfStore.templateApplyLoading" @update:value="(v) => { if (v) applyTemplate('opencode', v) }" />
                    <n-button size="small" @click="openTemplateManager('opencode')">{{ $t('enhance.manageTemplates') }}</n-button>
                  </div>
                  <n-alert type="info" :bordered="false" class="template-restart-alert">
                    {{ $t('enhance.templateRestartHint') }}
                  </n-alert>
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

      <!-- 自动拒绝改写说明 + 手动备用测试 -->
      <n-card v-if="anyCtfEnabled" :title="$t('enhance.autoRewriteFlow')" size="small">
        <n-space vertical>
          <n-alert type="success" :bordered="false">
            {{ $t('enhance.autoRewriteFlowDesc') }}
          </n-alert>
          <n-alert
            v-if="!settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
            type="warning"
            :bordered="false"
          >
            {{ $t('enhance.noAiConfig') }}
          </n-alert>

          <n-collapse>
            <n-collapse-item :title="$t('enhance.manualRewriteAdvanced')" name="manual-rewrite">
              <n-space vertical>
                <n-text depth="3" style="font-size: 13px; line-height: 1.6">
                  {{ $t('enhance.manualRewriteDesc') }}
                </n-text>

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
            </n-collapse-item>
          </n-collapse>
        </n-space>
      </n-card>

      <!-- 推荐工作流 -->
      <n-card :title="$t('help.workflow')" size="small">
        <n-tabs type="segment" size="small">
          <n-tab-pane name="codex" tab="Codex">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.ctfProfileDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="Profile: codex -p ctf; Global: codex" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.autoRewriteStepDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
          <n-tab-pane name="claude" tab="Claude Code">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.claudeDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="cd ~/.claude-ctf-workspace && claude" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.autoRewriteStepDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
          <n-tab-pane name="opencode" tab="OpenCode">
            <n-steps vertical :current="0" size="small" style="margin-top: 12px">
              <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.opencodeDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[1]')" description="cd ~/.opencode-ctf-workspace && opencode" />
              <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.autoRewriteStepDesc')" />
              <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
            </n-steps>
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </n-space>

    <!-- 模板管理 -->
    <n-modal v-model:show="templateManager.show" preset="card" :title="$t('enhance.templateManagement')" style="max-width: 860px">
      <n-space vertical size="small">
        <n-alert type="info" :bordered="false">
          {{ $t('enhance.templateManagementDesc') }}
        </n-alert>
        <div class="template-manager-current">
          <n-text strong>{{ $t('enhance.currentTemplate') }}：</n-text>
          <n-tag type="success" size="small" :bordered="false">{{ currentTemplateName(templateManager.tool) }}</n-tag>
        </div>
        <n-card size="small" class="template-editor-card">
          <template #header>
            <n-space align="center">
              <span>{{ templateEditor.editingOriginalName ? $t('enhance.editTemplate') : $t('enhance.newTemplate') }}</span>
              <n-tag v-if="templateEditor.editingOriginalName" size="tiny" :bordered="false">{{ templateEditor.editingOriginalName }}</n-tag>
            </n-space>
          </template>
          <n-space vertical size="small">
            <n-input
              v-model:value="templateEditor.name"
              :placeholder="$t('enhance.templateNameHint')"
              :maxlength="20"
              show-count
            />
            <n-input
              v-model:value="templateEditor.prompt"
              type="textarea"
              :rows="6"
              :placeholder="$t('enhance.templateContentHint')"
              style="font-family: monospace; font-size: 12px"
            />
            <n-space align="center">
              <n-button
                size="small"
                type="primary"
                :disabled="!templateEditor.name.trim() || !templateEditor.prompt.trim() || (!templateEditor.editingOriginalName && userTemplateCount(templateManager.tool) >= MAX_TEMPLATES)"
                @click="saveTemplateFromManager"
              >
                {{ templateEditor.editingOriginalName ? $t('enhance.updateTemplate') : $t('enhance.createTemplate') }}
              </n-button>
              <n-button size="small" @click="startNewTemplate(templateManager.tool)">{{ $t('enhance.newTemplate') }}</n-button>
              <n-button size="small" quaternary @click="useCurrentPromptInEditor(templateManager.tool)">
                {{ $t('enhance.useCurrentPrompt') }}
              </n-button>
              <n-text depth="3" class="template-limit-hint">
                {{ $t('enhance.templateLimitHint', { count: userTemplateCount(templateManager.tool), max: MAX_TEMPLATES }) }}
              </n-text>
            </n-space>
          </n-space>
        </n-card>
        <n-empty v-if="managerTemplates.length === 0" :description="$t('enhance.noTemplates')" size="small" />
        <div v-else class="template-manager-list">
          <div v-for="tpl in managerTemplates" :key="tpl.name" class="template-manager-row">
            <div class="template-manager-info">
              <div class="template-manager-title">
                <span>{{ tpl.name }}</span>
                <n-tag v-if="tpl.active || tpl.name === ctfStore.prompts[templateManager.tool]?.current_template" type="success" size="tiny" :bordered="false">{{ $t('enhance.templateActive') }}</n-tag>
                <n-tag :type="tpl.builtin ? 'info' : 'default'" size="tiny" :bordered="false">
                  {{ tpl.builtin ? $t('enhance.templateBuiltin') : $t('enhance.templateUser') }}
                </n-tag>
              </div>
            </div>
            <div class="template-manager-actions">
              <n-button size="tiny" type="primary" :disabled="tpl.name === ctfStore.prompts[templateManager.tool]?.current_template" :loading="ctfStore.templateApplyLoading" @click="applyTemplate(templateManager.tool, tpl.name)">
                {{ $t('enhance.applyTemplate') }}
              </n-button>
              <n-button v-if="!tpl.builtin" size="tiny" @click="editTemplate(templateManager.tool, tpl.name)">
                {{ $t('common.edit') }}
              </n-button>
              <n-button v-if="!tpl.builtin" size="tiny" type="error" ghost @click="confirmDeleteTemplate(templateManager.tool, tpl.name)">
                {{ $t('common.delete') }}
              </n-button>
            </div>
          </div>
        </div>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage, useDialog } from 'naive-ui'
import { useCTFStore } from '../stores/ctfStore'
import { useSettingsStore } from '../stores/settingsStore'
import { useSessionStore } from '../stores/sessionStore'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const ctfStore = useCTFStore()
const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()

// 任意 CTF 模式已启用时才显示改写功能
const anyCtfEnabled = computed(() =>
  ctfStore.anyCtfConfigured ||
  ctfStore.status?.claude_installed ||
  ctfStore.status?.opencode_installed
)

const codexModeLabel = computed(() => {
  const mode = ctfStore.status?.codex_mode
  if (mode === 'global') return t('enhance.modeGlobalActive')
  if (mode === 'profile') return t('enhance.modeProfileReady')
  if (mode === 'global_broken' || mode === 'profile_broken') return t('enhance.modeBroken')
  return t('enhance.modeOff')
})

const codexModeSummary = computed(() => {
  const mode = ctfStore.status?.codex_mode
  if (mode === 'global') return t('enhance.modeGlobalSummary')
  if (mode === 'profile') return t('enhance.modeProfileSummary')
  if (mode === 'global_broken' || mode === 'profile_broken') return t('enhance.modeBrokenSummary')
  return t('enhance.modeOffSummary')
})

const codexModeAdvice = computed(() => {
  const mode = ctfStore.status?.codex_mode
  if (mode === 'global') return t('enhance.modeGlobalAdvice')
  if (mode === 'profile') return t('enhance.modeProfileAdvice')
  if (mode === 'global_broken' || mode === 'profile_broken') return t('enhance.modeBrokenAdvice')
  return t('enhance.modeOffAdvice')
})

const codexModeTagType = computed(() => {
  const mode = ctfStore.status?.codex_mode
  if (mode === 'global') return 'success'
  if (mode === 'profile') return 'info'
  if (mode === 'global_broken' || mode === 'profile_broken') return 'warning'
  return 'default'
})

const codexModeAlertType = computed(() => {
  const mode = ctfStore.status?.codex_mode
  if (mode === 'global') return 'success'
  if (mode === 'profile') return 'info'
  if (mode === 'global_broken' || mode === 'profile_broken') return 'warning'
  return 'default'
})

const ctfActiveSessions = computed(() =>
  sessionStore.codexSessions.filter(session => session.ctf_active)
)
const visibleCtfActiveSessions = computed(() => ctfActiveSessions.value.slice(0, 6))
const codexSessionCount = computed(() => sessionStore.codexSessions.length)
const ctfActiveCount = computed(() => ctfActiveSessions.value.length)
const ctfInactiveCount = computed(() => Math.max(codexSessionCount.value - ctfActiveCount.value, 0))
const ctfActiveMoreCount = computed(() => Math.max(ctfActiveCount.value - visibleCtfActiveSessions.value.length, 0))

const MAX_TEMPLATES = 5

const rewriteInput = ref('')
const codexPromptText = ref('')
const codexSelectedTemplate = ref(null)
const claudePromptText = ref('')
const claudeSelectedTemplate = ref(null)
const opencodePromptText = ref('')
const opencodeSelectedTemplate = ref(null)
const templateManager = ref({ show: false, tool: 'codex' })
const templateEditor = ref({ name: '', prompt: '', editingOriginalName: '' })
const managerTemplates = computed(() => ctfStore.templates[templateManager.value.tool] || [])

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
    if (ctfStore.prompts[tool].current_template) {
      getSelectedTemplateRef(tool).value = ctfStore.prompts[tool].current_template
    } else if (ctfStore.prompts[tool].is_default) {
      const defaultTpl = ctfStore.templates[tool].find(t => t.default === true)
      if (defaultTpl) getSelectedTemplateRef(tool).value = defaultTpl.name
    }
  }
})

async function refreshSessions() {
  await sessionStore.fetchSessions()
}

function formatSessionMeta(session) {
  const project = session.project_path ? truncate(session.project_path, 32) : ''
  const time = session.mtime || ''
  return project ? `${project} · ${time}` : time
}

function truncate(text, maxLength) {
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

// ─── 模板相关 ──────────────────────────────────────────

function templateOptions(tool) {
  return ctfStore.templates[tool].map(tpl => ({
    label: tpl.name,
    value: tpl.name,
    builtin: tpl.builtin || false,
    active: tpl.active || tpl.name === ctfStore.prompts[tool]?.current_template,
  }))
}

function renderTemplateLabel(option, tool) {
  const children = [
    h('span', {
      style: 'flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap',
    }, option.label),
  ]
  if (option.active) {
    children.push(h('span', {
      style: 'font-size:11px; color:#18a058; flex-shrink:0',
    }, t('enhance.templateActive')))
  }
  return h('div', {
    style: 'display:flex; align-items:center; justify-content:space-between; width:100%; gap:8px',
  }, children)
}

async function applyTemplate(tool, templateName) {
  if (!templateName) return
  getSelectedTemplateRef(tool).value = templateName
  const result = await ctfStore.applyTemplate(tool, templateName)
  if (result.success) {
    getPromptTextRef(tool).value = ctfStore.prompts[tool].prompt
    getSelectedTemplateRef(tool).value = ctfStore.prompts[tool].current_template || templateName
    const hints = Array.isArray(result.restart_hints) && result.restart_hints.length > 0
      ? `\n${result.restart_hints.join('\n')}`
      : ''
    message.success(`${result.message || t('enhance.templateApplied')}${hints}`, { duration: 6000, keepAliveOnHover: true })
  } else {
    message.error(result.message || t('enhance.templateApplyFailed'))
  }
}

function openTemplateManager(tool) {
  templateManager.value = { show: true, tool }
  startNewTemplate(tool)
}

function currentTemplateName(tool) {
  return ctfStore.prompts[tool]?.current_template || t('enhance.unnamedCustomTemplate')
}

function userTemplateCount(tool) {
  return (ctfStore.templates[tool] || []).filter(tpl => !tpl.builtin).length
}

function startNewTemplate(tool) {
  templateEditor.value = {
    name: '',
    prompt: getPromptTextRef(tool).value || ctfStore.prompts[tool]?.prompt || '',
    editingOriginalName: '',
  }
}

function useCurrentPromptInEditor(tool) {
  templateEditor.value.prompt = getPromptTextRef(tool).value || ctfStore.prompts[tool]?.prompt || ''
}

async function editTemplate(tool, name) {
  const tpl = (ctfStore.templates[tool] || []).find(item => item.name === name)
  if (!tpl || tpl.builtin) return
  const prompt = await ctfStore.fetchTemplatePrompt(tool, name)
  templateEditor.value = {
    name,
    prompt,
    editingOriginalName: name,
  }
}

async function saveTemplateFromManager() {
  const tool = templateManager.value.tool
  const name = templateEditor.value.name.trim()
  const prompt = templateEditor.value.prompt.trim()
  if (!name || !prompt) return

  const oldName = templateEditor.value.editingOriginalName || null
  const activeBefore = ctfStore.prompts[tool]?.current_template
  const result = await ctfStore.saveTemplate(tool, name, prompt, oldName)
  if (result.success) {
    templateEditor.value.editingOriginalName = name
    message.success(oldName ? t('enhance.templateUpdated') : t('enhance.templateSaved'))
    if (activeBefore && (activeBefore === oldName || activeBefore === name)) {
      await applyTemplate(tool, name)
    }
  } else {
    message.error(result.message)
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
        if (getSelectedTemplateRef(tool).value === name) {
          getSelectedTemplateRef(tool).value = ctfStore.prompts[tool]?.current_template || null
        }
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
    getSelectedTemplateRef(tool).value = ctfStore.prompts[tool].current_template || null
    message.success(t('enhance.promptSaved'))
  } else {
    message.error(result.message || t('enhance.promptSaveError'))
  }
}

async function handleResetPrompt(tool) {
  const result = await ctfStore.resetPromptToDefault(tool)
  if (result.success) {
    getPromptTextRef(tool).value = ctfStore.prompts[tool].prompt
    getSelectedTemplateRef(tool).value = ctfStore.prompts[tool].current_template || null
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

async function handleLaunchCodex() {
  if (sessionStore.codexSessions.length === 0) {
    await sessionStore.fetchSessions(false)
  }
  const launchCwd = sessionStore.codexSessions.find(session => session.project_path)?.project_path || null
  const result = await ctfStore.launchCodex(launchCwd)
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

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text || '')
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

.status-overview {
  border: 1px solid rgba(128, 128, 128, 0.18);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 14px;
  background: rgba(128, 128, 128, 0.06);
}

.status-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.status-subtitle {
  margin-top: 4px;
  color: var(--n-text-color-3);
  font-size: 13px;
  line-height: 1.5;
}

.mode-alert {
  margin-top: 10px;
}

.status-command-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--n-text-color-3);
}

.profile-session-box {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid rgba(128, 128, 128, 0.16);
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.05);
}

.profile-session-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.profile-session-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.profile-session-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-session-summary,
.profile-session-inactive,
.profile-session-more {
  color: var(--n-text-color-3);
  font-size: 12px;
  line-height: 1.5;
}

.profile-session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.profile-session-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) auto minmax(120px, 1.6fr);
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 6px;
  background: rgba(24, 160, 88, 0.1);
}

.profile-session-id {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
  font-size: 12px;
  color: var(--n-text-color-1);
}

.profile-session-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--n-text-color-3);
  font-size: 12px;
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
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.template-current-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}

.template-active-hint {
  font-size: 12px;
}

.template-restart-alert {
  margin-bottom: 8px;
}

.template-manager-current {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-editor-card {
  background: rgba(128, 128, 128, 0.04);
}

.template-limit-hint {
  font-size: 12px;
}

.template-manager-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-manager-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(128, 128, 128, 0.16);
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.05);
}

.template-manager-info {
  min-width: 0;
  flex: 1;
}

.template-manager-title,
.template-manager-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
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
