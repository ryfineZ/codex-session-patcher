import { defineStore } from 'pinia'
import { api, clearCache } from '../services/api'

export const useCTFStore = defineStore('ctf', {
  state: () => ({
    // CTF 配置状态
    status: null,
    loading: false,
    installLoading: false,
    globalInstallLoading: false,
    launchLoading: false,
    claudeInstallLoading: false,
    opencodeInstallLoading: false,
    templateApplyLoading: false,

    // 提示词改写
    originalRequest: '',
    rewrittenRequest: '',
    rewriteStrategy: '',
    rewriteLoading: false,
    rewriteError: null,
    rewriteTarget: 'codex',  // 'codex' | 'claude_code'

    // CTF 提示词内容
    prompts: {
      codex: { prompt: '', is_default: true, is_installed: false, current_template: null, loading: false },
      claude_code: { prompt: '', is_default: true, is_installed: false, current_template: null, loading: false },
      opencode: { prompt: '', is_default: true, is_installed: false, current_template: null, loading: false },
    },

    // CTF 提示词模板
    templates: {
      codex: [],
      claude_code: [],
      opencode: [],
    },
  }),

  getters: {
    codexRuntimeEnabled: (state) => state.status?.codex_mode === 'global',
    codexProfileReady: (state) => state.status?.codex_mode === 'profile',
    codexBroken: (state) => ['profile_broken', 'global_broken'].includes(state.status?.codex_mode),
    anyCtfConfigured: (state) => (
      ['profile', 'global', 'profile_broken', 'global_broken'].includes(state.status?.codex_mode) ||
      state.status?.claude_installed ||
      state.status?.opencode_installed
    ),
    anyRuntimeAutoActive: (state) => state.status?.codex_mode === 'global',
  },

  actions: {
    // 获取 CTF 配置状态
    async fetchStatus() {
      this.loading = true
      // 清除缓存确保获取最新状态
      clearCache('ctf/status')
      try {
        const response = await api.get('/ctf/status')
        this.status = response
      } catch (error) {
        console.error('获取 CTF 配置状态失败:', error)
      } finally {
        this.loading = false
      }
    },

    // 安装 CTF 配置
    async install() {
      this.installLoading = true
      try {
        const response = await api.post('/ctf/install')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.installLoading = false
      }
    },

    // 卸载 CTF 配置
    async uninstall() {
      this.installLoading = true
      try {
        const response = await api.post('/ctf/uninstall')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.installLoading = false
      }
    },

    // 启用全局模式 (Codex)
    async installGlobal() {
      this.globalInstallLoading = true
      try {
        const response = await api.post('/ctf/global/install')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.globalInstallLoading = false
      }
    },

    // 禁用全局模式 (Codex)
    async uninstallGlobal() {
      this.globalInstallLoading = true
      try {
        const response = await api.post('/ctf/global/uninstall')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.globalInstallLoading = false
      }
    },

    // 安装 Claude Code CTF 配置
    async launchCodex(cwd = null) {
      this.launchLoading = true
      try {
        return await api.post('/ctf/codex/launch', cwd ? { cwd } : {})
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.launchLoading = false
      }
    },

    async installClaude() {
      this.claudeInstallLoading = true
      try {
        const response = await api.post('/ctf/claude/install')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.claudeInstallLoading = false
      }
    },

    // 卸载 Claude Code CTF 配置
    async uninstallClaude() {
      this.claudeInstallLoading = true
      try {
        const response = await api.post('/ctf/claude/uninstall')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.claudeInstallLoading = false
      }
    },

    // 安装 OpenCode CTF 配置
    async installOpencode() {
      this.opencodeInstallLoading = true
      try {
        const response = await api.post('/ctf/opencode/install')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.opencodeInstallLoading = false
      }
    },

    // 卸载 OpenCode CTF 配置
    async uninstallOpencode() {
      this.opencodeInstallLoading = true
      try {
        const response = await api.post('/ctf/opencode/uninstall')
        if (response.success && response.status) {
          this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.opencodeInstallLoading = false
      }
    },

    // 获取 CTF 提示词
    async fetchPrompt(tool) {
      if (!this.prompts[tool]) return
      this.prompts[tool].loading = true
      try {
        const response = await api.get(`/ctf/prompt/${tool}`)
        this.prompts[tool].prompt = response.prompt
        this.prompts[tool].is_default = response.is_default
        this.prompts[tool].is_installed = response.is_installed
        this.prompts[tool].current_template = response.current_template || null
      } catch (error) {
        console.error(`获取 ${tool} 提示词失败:`, error)
      } finally {
        this.prompts[tool].loading = false
      }
    },

    // 保存 CTF 提示词
    async savePrompt(tool, prompt) {
      try {
        const response = await api.post(`/ctf/prompt/${tool}`, { prompt })
        if (response.success) {
          this.prompts[tool].prompt = prompt
          this.prompts[tool].is_default = false
          this.prompts[tool].current_template = response.current_template || null
          if (response.status) this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      }
    },

    // 获取模板列表
    async fetchTemplates(tool) {
      try {
        const response = await api.get(`/ctf/prompt/${tool}/templates`)
        this.templates[tool] = response.templates || []
        if (this.prompts[tool]) {
          this.prompts[tool].current_template = response.current_template || this.prompts[tool].current_template || null
        }
      } catch (error) {
        console.error(`获取 ${tool} 模板失败:`, error)
      }
    },

    // 获取单个模板的 prompt 内容
    async fetchTemplatePrompt(tool, templateName) {
      const response = await api.get(`/ctf/prompt/${tool}/templates/${encodeURIComponent(templateName)}`)
      return response.prompt || ''
    },

    // 保存当前内容为模板
    async saveTemplate(tool, name, prompt, oldName = null) {
      try {
        const response = await api.post(`/ctf/prompt/${tool}/templates`, { name, prompt, old_name: oldName })
        if (response.success) {
          this.templates[tool] = response.templates || []
          if (this.prompts[tool]) this.prompts[tool].current_template = response.current_template || null
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      }
    },

    // 删除模板
    async deleteTemplate(tool, templateName) {
      try {
        const response = await api.delete(`/ctf/prompt/${tool}/templates/${encodeURIComponent(templateName)}`)
        if (response.success) {
          this.templates[tool] = response.templates || []
          if (this.prompts[tool]) this.prompts[tool].current_template = response.current_template || null
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      }
    },

    // 切换模板并立即写入当前已启用配置
    async applyTemplate(tool, templateName) {
      this.templateApplyLoading = true
      try {
        clearCache(`ctf/prompt/${tool}`)
        const response = await api.post(`/ctf/prompt/${tool}/templates/${encodeURIComponent(templateName)}/apply`)
        if (response.success) {
          this.templates[tool] = response.templates || this.templates[tool]
          this.prompts[tool].prompt = response.prompt || ''
          this.prompts[tool].is_default = this.templates[tool].some(t => t.default && t.name === response.current_template)
          this.prompts[tool].is_installed =
            Boolean(response.status?.codex_profile_ready || response.status?.codex_global_active) ||
            Boolean(response.status?.claude_installed && tool === 'claude_code') ||
            Boolean(response.status?.opencode_installed && tool === 'opencode')
          this.prompts[tool].current_template = response.current_template || templateName
          if (response.status) this.status = response.status
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.templateApplyLoading = false
      }
    },

    // 恢复默认提示词
    async resetPromptToDefault(tool) {
      try {
        const response = await api.post(`/ctf/prompt/${tool}/reset`)
        if (response.success) {
          this.prompts[tool].prompt = response.prompt
          this.prompts[tool].is_default = true
          this.prompts[tool].current_template = null
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      }
    },

    // 改写提示词
    async rewritePrompt(originalRequest, target = null) {
      this.rewriteLoading = true
      this.rewriteError = null
      this.originalRequest = originalRequest

      try {
        const response = await api.post('/prompt-rewrite', {
          original_request: originalRequest,
          target: target || this.rewriteTarget,
        })

        if (response.success) {
          this.rewrittenRequest = response.rewritten
          this.rewriteStrategy = response.strategy
        } else {
          this.rewriteError = response.error
        }

        return response
      } catch (error) {
        this.rewriteError = error.message
        return { success: false, error: error.message }
      } finally {
        this.rewriteLoading = false
      }
    },

    // 重置改写状态
    resetRewrite() {
      this.originalRequest = ''
      this.rewrittenRequest = ''
      this.rewriteStrategy = ''
      this.rewriteError = null
    }
  }
})
