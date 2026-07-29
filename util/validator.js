/**
 * 参数校验工具模块
 * 提供统一的参数校验函数，在每个路由入口调用
 */

// 手机号正则（中国大陆）
const PHONE_REGEX = /^1[3-9]\d{9}$/

// 验证码正则（4-6位数字）
const CODE_REGEX = /^\d{4,6}$/

/**
 * 校验必填字段
 * @param {object} data - 请求数据
 * @param {string[]} fields - 必填字段列表
 * @returns {{ valid: boolean, missing: string[] }}
 */
function validateRequired(data, fields) {
  const missing = []
  for (const field of fields) {
    const val = data[field]
    if (val === undefined || val === null || (typeof val === 'string' && val.trim() === '')) {
      missing.push(field)
    }
  }
  return { valid: missing.length === 0, missing }
}

/**
 * 校验手机号
 * @param {string} phone - 手机号
 * @returns {{ valid: boolean, message: string }}
 */
function validatePhone(phone) {
  if (!phone) return { valid: false, message: '手机号不能为空' }
  if (!PHONE_REGEX.test(phone)) return { valid: false, message: '手机号格式不正确' }
  return { valid: true, message: '' }
}

/**
 * 校验验证码
 * @param {string} code - 验证码
 * @returns {{ valid: boolean, message: string }}
 */
function validateCode(code) {
  if (!code) return { valid: false, message: '验证码不能为空' }
  if (!CODE_REGEX.test(code)) return { valid: false, message: '验证码格式不正确（4-6位数字）' }
  return { valid: true, message: '' }
}

/**
 * 校验字符串长度
 * @param {string} str - 字符串
 * @param {number} min - 最小长度
 * @param {number} max - 最大长度
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {{ valid: boolean, message: string }}
 */
function validateLength(str, min, max, fieldName) {
  if (!str || typeof str !== 'string') return { valid: false, message: `${fieldName} 不能为空` }
  const trimmed = str.trim()
  if (trimmed.length < min) return { valid: false, message: `${fieldName} 长度不能少于 ${min} 个字符` }
  if (trimmed.length > max) return { valid: false, message: `${fieldName} 长度不能超过 ${max} 个字符` }
  return { valid: true, message: '' }
}

/**
 * 校验数字ID
 * @param {*} id - ID值
 * @param {string} fieldName - 字段名称
 * @returns {{ valid: boolean, message: string }}
 */
function validateId(id, fieldName) {
  if (id === undefined || id === null || id === '') {
    return { valid: false, message: `${fieldName} 不能为空` }
  }
  const num = Number(id)
  if (isNaN(num) || num < 0 || !Number.isInteger(num)) {
    return { valid: false, message: `${fieldName} 必须是有效的数字ID` }
  }
  return { valid: true, message: '' }
}

/**
 * 批量校验并返回第一个错误
 * @param {...{ valid: boolean, message: string }} results - 校验结果
 * @returns {{ valid: boolean, message: string }}
 */
function validateAll(...results) {
  for (const r of results) {
    if (!r.valid) return r
  }
  return { valid: true, message: '' }
}

module.exports = {
  validateRequired,
  validatePhone,
  validateCode,
  validateLength,
  validateId,
  validateAll,
  PHONE_REGEX,
  CODE_REGEX,
}
