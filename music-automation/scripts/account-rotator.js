/**
 * 账号轮换管理器
 * 智能管理多账号的登录状态和任务分配
 */

const { getModulesDefinitions } = require('../../../server')
const logger = require('../../../util/logger')

class AccountRotator {
  constructor(interpreter, ncmApi) {
    this.interpreter = interpreter
    this.ncmApi = ncmApi
    this.accountPool = new Map()
    this.rotationStrategy = 'round-robin' // round-robin, load-based, priority-based
    this.healthCheckInterval = 300000 // 5分钟
  }

  /**
   * 初始化账号池
   */
  async initializeAccountPool(accountIds) {
    logger.info('初始化账号池', { accountCount: accountIds.length })
    
    for (const accountId of accountIds) {
      const account = {
        id: accountId,
        status: 'initializing',
        lastActivity: Date.now(),
        taskCount: 0,
        successRate: 1.0,
        healthScore: 100,
        rotationCount: 0
      }
      
      this.accountPool.set(accountId, account)
    }
    
    // 启动健康检查
    this.startHealthCheck()
    
    return this.accountPool
  }

  /**
   * 获取下一个可用账号
   */
  async getNextAvailableAccount() {
    const availableAccounts = Array.from(this.accountPool.values())
      .filter(acc => acc.status === 'online' && acc.healthScore > 50)
    
    if (availableAccounts.length === 0) {
      throw new Error('没有可用的账号')
    }
    
    let selectedAccount
    
    switch (this.rotationStrategy) {
      case 'round-robin':
        selectedAccount = this.selectRoundRobin(availableAccounts)
        break
      case 'load-based':
        selectedAccount = this.selectLoadBased(availableAccounts)
        break
      case 'priority-based':
        selectedAccount = this.selectPriorityBased(availableAccounts)
        break
      default:
        selectedAccount = availableAccounts[0]
    }
    
    // 更新账号状态
    selectedAccount.lastActivity = Date.now()
    selectedAccount.taskCount++
    selectedAccount.rotationCount++
    
    logger.info('选择账号', { 
      accountId: selectedAccount.id, 
      strategy: this.rotationStrategy,
      healthScore: selectedAccount.healthScore 
    })
    
    return selectedAccount
  }

  /**
   * 轮询选择策略
   */
  selectRoundRobin(accounts) {
    const sorted = accounts.sort((a, b) => a.rotationCount - b.rotationCount)
    return sorted[0]
  }

  /**
   * 负载均衡选择策略
   */
  selectLoadBased(accounts) {
    const sorted = accounts.sort((a, b) => {
      const scoreA = a.healthScore / (a.taskCount + 1)
      const scoreB = b.healthScore / (b.taskCount + 1)
      return scoreB - scoreA
    })
    return sorted[0]
  }

  /**
   * 优先级选择策略
   */
  selectPriorityBased(accounts) {
    const sorted = accounts.sort((a, b) => {
      const priorityA = a.healthScore * a.successRate
      const priorityB = b.healthScore * b.successRate
      return priorityB - priorityA
    })
    return sorted[0]
  }

  /**
   * 执行账号轮换任务
   */
  async executeRotationTask(taskConfig) {
    const { targetAccounts, taskType, parameters } = taskConfig
    
    try {
      logger.info('开始账号轮换任务', { 
        taskType, 
        targetCount: targetAccounts.length 
      })
      
      const results = []
      
      for (const targetAccount of targetAccounts) {
        try {
          const account = await this.getNextAvailableAccount()
          
          // 使用 AI 执行任务
          const result = await this.interpreter.execute(`
            // 执行账号轮换任务
            const taskResult = await this.executeAccountRotation({
              sourceAccount: "${account.id}",
              targetAccount: "${targetAccount}",
              taskType: "${taskType}",
              parameters: ${JSON.stringify(parameters)},
              ncmApi: this.ncmApi
            })
            
            // 更新账号状态
            this.updateAccountHealth("${account.id}", taskResult.success)
            
            return {
              success: true,
              sourceAccount: "${account.id}",
              targetAccount: "${targetAccount}",
              result: taskResult
            }
          `)
          
          results.push(result)
          
        } catch (error) {
          logger.error('账号轮换失败', { 
            targetAccount, 
            error: error.message 
          })
          
          results.push({
            success: false,
            targetAccount,
            error: error.message
          })
        }
      }
      
      logger.info('账号轮换任务完成', { 
        success: results.filter(r => r.success).length,
        failed: results.filter(r => !r.success).length 
      })
      
      return results
      
    } catch (error) {
      logger.error('账号轮换任务失败', { error: error.message })
      throw error
    }
  }

  /**
   * 健康检查
   */
  async performHealthCheck(accountId) {
    const account = this.accountPool.get(accountId)
    
    try {
      // 检查账号登录状态
      const loginStatus = await this.ncmApi.login_status()
      
      // 更新健康分数
      let healthScore = account.healthScore
      
      if (loginStatus.code === 200) {
        healthScore = Math.min(100, healthScore + 5)
      } else {
        healthScore = Math.max(0, healthScore - 20)
      }
      
      // 更新账号状态
      account.status = loginStatus.code === 200 ? 'online' : 'offline'
      account.healthScore = healthScore
      
      logger.info('账号健康检查', { 
        accountId, 
        status: account.status, 
        healthScore: healthScore 
      })
      
    } catch (error) {
      logger.error('账号健康检查失败', { accountId, error: error.message })
      account.healthScore = Math.max(0, account.healthScore - 10)
    }
  }

  /**
   * 启动健康检查
   */
  startHealthCheck() {
    setInterval(async () => {
      for (const accountId of this.accountPool.keys()) {
        await this.performHealthCheck(accountId)
      }
    }, this.healthCheckInterval)
  }

  /**
   * 更新账号健康状态
   */
  updateAccountHealth(accountId, success) {
    const account = this.accountPool.get(accountId)
    
    if (success) {
      account.successRate = (account.successRate * 0.9) + 0.1
      account.healthScore = Math.min(100, account.healthScore + 2)
    } else {
      account.successRate = (account.successRate * 0.9)
      account.healthScore = Math.max(0, account.healthScore - 10)
    }
    
    account.lastActivity = Date.now()
  }

  /**
   * 获取账号池状态
   */
  getAccountPoolStatus() {
    const status = {
      totalAccounts: this.accountPool.size,
      onlineAccounts: Array.from(this.accountPool.values()).filter(acc => acc.status === 'online').length,
      offlineAccounts: Array.from(this.accountPool.values()).filter(acc => acc.status === 'offline').length,
      averageHealthScore: Array.from(this.accountPool.values()).reduce((sum, acc) => sum + acc.healthScore, 0) / this.accountPool.size,
      averageSuccessRate: Array.from(this.accountPool.values()).reduce((sum, acc) => sum + acc.successRate, 0) / this.accountPool.size
    }
    
    return status
  }
}

module.exports = AccountRotator