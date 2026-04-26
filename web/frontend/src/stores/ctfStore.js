import { defineStore } from 'pinia'
import { api, clearCache } from '../services/api'

export const useCTFStore = defineStore('ctf', {
  state: () => ({
    // CTF 配置状态
    status: null,
    loading: false,
    installLoading: false,
    globalInstallLoading: false,
    claudeInstallLoading: false,
    opencodeInstallLoading: false,

    // 提示词改写
    originalRequest: '',
    rewrittenRequest: '',
    rewriteStrategy: '',
    rewriteLoading: false,
    rewriteError: null,
    rewriteTarget: 'codex',  // 'codex' | 'claude_code'

    // CTF 提示词内容
    prompts: {
      codex: { prompt: '', is_default: true, is_installed: false, loading: false },
      claude_code: { prompt: '', is_default: true, is_installed: false, loading: false },
      opencode: { prompt: '', is_default: true, is_installed: false, loading: false },
    },

    // CTF 提示词模板
    templates: {
      codex: [],
      claude_code: [],
      opencode: [],
    },
  }),

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
    async saveTemplate(tool, name, prompt) {
      try {
        const response = await api.post(`/ctf/prompt/${tool}/templates`, { name, prompt })
        if (response.success) {
          this.templates[tool] = response.templates
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
          this.templates[tool] = response.templates
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      }
    },

    // 恢复默认提示词
    async resetPromptToDefault(tool) {
      try {
        const response = await api.post(`/ctf/prompt/${tool}/reset`)
        if (response.success) {
          this.prompts[tool].prompt = response.prompt
          this.prompts[tool].is_default = true
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
