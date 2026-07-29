// ANSI 颜色代码
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  black: '\x1b[30m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
}

// 敏感字段列表（需要脱敏）
const SENSITIVE_KEYS = [
  'cookie', 'MUSIC_U', 'MUSIC_A', '__csrf',
  'password', 'token', 'secret', 'key', 'csrf_token',
  'captcha', 'code',
]

// 脱敏函数：将敏感值替换为 ***
function sanitize(obj) {
  if (!obj || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(sanitize)
  const cleaned = {}
  for (const [k, v] of Object.entries(obj)) {
    if (SENSITIVE_KEYS.includes(k) || k.toLowerCase().includes('cookie')) {
      cleaned[k] = '***'
    } else if (typeof v === 'object' && v !== null) {
      cleaned[k] = sanitize(v)
    } else {
      cleaned[k] = v
    }
  }
  return cleaned
}

// JSON 结构化日志
function jsonLog(level, msg, data) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    message: msg,
  }
  if (data) {
    entry.data = sanitize(data)
  }
  return JSON.stringify(entry)
}

// 控制台彩色输出快捷函数
function colorLog(level, msg, data) {
  const json = jsonLog(level, msg, data)
  let colorFn
  switch (level) {
    case 'INFO': colorFn = `${colors.green}[INFO]${colors.reset}`; break
    case 'WARN': colorFn = `${colors.yellow}[WARN]${colors.reset}`; break
    case 'ERROR': colorFn = `${colors.red}[ERROR]${colors.reset}`; break
    case 'SUCCESS': colorFn = `${colors.bright}${colors.green}[SUCCESS]${colors.reset}`; break
    case 'CRITICAL': colorFn = `${colors.bright}${colors.bgRed}[CRITICAL]${colors.reset}`; break
    default: colorFn = `${colors.cyan}[DEBUG]${colors.reset}`
  }
  if (level === 'ERROR' || level === 'CRITICAL') {
    console.error(`${colorFn} ${json}`)
  } else {
    console.log(`${colorFn} ${json}`)
  }
}

const logger = {
  debug: (msg, data) => colorLog('DEBUG', msg, data),
  info: (msg, data) => colorLog('INFO', msg, data),
  warn: (msg, data) => colorLog('WARN', msg, data),
  error: (msg, data) => colorLog('ERROR', msg, data),
  success: (msg, data) => colorLog('SUCCESS', msg, data),
  critical: (msg, data) => colorLog('CRITICAL', msg, data),
  json: jsonLog,
  sanitize,
}

module.exports = logger
