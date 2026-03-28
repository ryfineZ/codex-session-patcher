import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useCTFStore = defineStore('ctf', {
  state: () => ({
    // CTF 配置状态
    status: null,
    loading: false,
    installLoading: false,
    claudeInstallLoading: false,

    // 提示词改写
    originalRequest: '',
    rewrittenRequest: '',
    rewriteStrategy: '',
    rewriteLoading: false,
    rewriteError: null,
    rewriteTarget: 'codex',  // 'codex' | 'claude_code'
  }),

  actions: {
    // 获取 CTF 配置状态
    async fetchStatus() {
      this.loading = true
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
        if (response.success) {
          await this.fetchStatus()
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
        if (response.success) {
          await this.fetchStatus()
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.installLoading = false
      }
    },

    // 安装 Claude Code CTF 配置
    async installClaude() {
      this.claudeInstallLoading = true
      try {
        const response = await api.post('/ctf/claude/install')
        if (response.success) {
          await this.fetchStatus()
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
        if (response.success) {
          await this.fetchStatus()
        }
        return response
      } catch (error) {
        return { success: false, message: error.message }
      } finally {
        this.claudeInstallLoading = false
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