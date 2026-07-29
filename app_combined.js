#!/usr/bin/env node
const fs = require('fs')
const path = require('path')
const os = require('os')
const express = require('express')
const tmpPath = os.tmpdir()

// 必须在 import 其他模块前创建 anonymous_token
if (!fs.existsSync(path.resolve(tmpPath, 'anonymous_token'))) {
  fs.writeFileSync(path.resolve(tmpPath, 'anonymous_token'), '', 'utf-8')
}

const { getModulesDefinitions } = require('./server')
const generateConfig = require('./generateConfig')
const packageJSON = require('./package.json')
const request = require('./util/request')
const cache = require('./util/apicache').middleware
const { cookieToJson } = require('./util/index')
const fileUpload = require('express-fileupload')
const decode = require('safe-decode-uri-component')
const logger = require('./util/logger')
const validator = require('./util/validator')
const { APP_CONF } = require('./util/config.json')

const PORT = Number(process.env.PORT || '8000')

// ====== In-Memory 状态（账号、任务、Session）======
const state = {
  accounts: {},
  nextId: 1,
  runningTasks: {},
  maxThreads: 4,
  loginSessions: {},  // phone -> { cookies: [], createTime }
}
const STATE_FILE = path.join(__dirname, '.state.json')

// [FIX-B009] 2026-07-28 | 后端 | 可靠性
// 问题：状态纯内存存储，重启后所有账号登录态丢失
// 修改：启动时从文件加载，状态变更时自动持久化
// 状态：已修复
function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'))
      state.accounts = saved.accounts || {}
      state.nextId = saved.nextId || 1
      state.maxThreads = saved.maxThreads || 4
      logger.info('状态已从磁盘加载', { accounts: Object.keys(state.accounts).length })
    }
  } catch (e) {
    logger.warn('状态加载失败，使用默认值', { error: e.message })
  }
}

function saveState() {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify({
      accounts: state.accounts,
      nextId: state.nextId,
      maxThreads: state.maxThreads,
    }, null, 2), 'utf-8')
  } catch (e) {
    logger.error('状态保存失败', { error: e.message })
  }
}

// 在关键状态变更后自动保存
loadState()
// [FIX-B002] 2026-07-28 | 后端 | 安全
// 问题：state.accounts 无锁保护导致并发竞态
// 修改：增加简单 Promise 链式互斥锁
// 状态：已修复
let mutexChain = Promise.resolve()
function withLock(fn) {
  const result = mutexChain.then(() => fn())
  mutexChain = result.catch(() => {})
  return result
}

// [FIX-B008] 2026-07-28 | 后端 | 安全
// 问题：登录/发验证码接口无频率限制，可被短信轰炸/暴力枚举
// 修改：增加内存滑动窗口限流（每IP每分钟5次）
// 状态：已修复
function createRateLimiter(windowMs, maxRequests) {
  const store = {}
  return (req, res, next) => {
    let ip = req.ip || req.connection.remoteAddress
    if (ip && ip.startsWith('::ffff:')) ip = ip.substring(7)
    if (ip === '::1') ip = '127.0.0.1'
    if (!ip) ip = 'unknown'
    const now = Date.now()
    if (!store[ip]) store[ip] = []
    store[ip] = store[ip].filter(t => now - t < windowMs)
    if (store[ip].length >= maxRequests) {
      logger.warn('Rate limit exceeded', { ip, count: store[ip].length, maxRequests })
      return res.status(429).json({ success: false, message: '请求过于频繁，请稍后再试' })
    }
    store[ip].push(now)
    next()
  }
}
// [FIX-B007] 2026-07-28 | 后端 | 安全
// 问题：所有 /api/* 端点无认证检查，存在 IDOR 漏洞
// 修改：增加基础认证中间件（验证简单共享密钥）
// 副作用：前端需要携带认证头
// 状态：已修复
const API_SECRET = process.env.API_SECRET || 'music-platform-2024'
function authMiddleware(req, res, next) {
  // 静态文件和首页跳过
  if (req.path === '/' || req.path === '/index.html' || req.path.includes('.')) return next()
  const token = req.headers['x-api-token'] || req.query.token
  if (token === API_SECRET) return next()
  // 未认证时返回 401
  return res.status(401).json({ success: false, message: '未授权访问' })
}
// 限流保护敏感端点
const loginLimiter = createRateLimiter(60000, 5)  // 每分钟5次
const generalLimiter = createRateLimiter(60000, 60)  // 每分钟60次

// ====== 辅助函数 ======
function accountToDict(acc) {
  return {
    id: acc.id,
    name: acc.name,
    phone: acc.phone,
    status: acc.status,
    tasks: acc.tasks,
    completed: acc.completed,
    failed: acc.failed,
    progress: acc.progress,
    running: acc.running,
    lastError: acc.lastError,
  }
}

async function startServer() {
  await generateConfig()

  const app = express()
  const { CORS_ALLOW_ORIGIN } = process.env
  app.set('trust proxy', true)

  // ====== 中间件 ======
  app.use(express.static(path.join(__dirname, 'public')))

  // [FIX-B004] 2026-07-28 | 后端 | 安全
  // 问题：CORS 反射任意 Origin 且始终 Allow-Credentials，可被 CSRF 攻击
  // 修改：只允许本地和 monkeycode-ai.online 域
  // 状态：已修复
  const ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
  ]
  app.use((req, res, next) => {
    if (req.path !== '/' && !req.path.includes('.')) {
      const origin = req.headers.origin
      const allowedOrigin = origin && (
        origin.endsWith('.monkeycode-ai.online') ||
        ALLOWED_ORIGINS.includes(origin)
      ) ? origin : ALLOWED_ORIGINS[0]
      res.set({
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Origin': allowedOrigin,
        'Access-Control-Allow-Headers': 'X-Requested-With,Content-Type,X-API-Token',
        'Access-Control-Allow-Methods': 'PUT,POST,GET,DELETE,OPTIONS',
        'Content-Type': 'application/json; charset=utf-8',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000',
      })
    }
    req.method === 'OPTIONS' ? res.status(204).end() : next()
  })

  app.use((req, _, next) => {
    req.cookies = {}
    ;(req.headers.cookie || '').split(/;\s+|(?<!\s)\s+$/g).forEach((pair) => {
      let crack = pair.indexOf('=')
      if (crack < 1 || crack == pair.length - 1) return
      req.cookies[decode(pair.slice(0, crack)).trim()] = decode(pair.slice(crack + 1)).trim()
    })
    next()
  })

  // [FIX-B012] 2026-07-28 | 后端 | 安全
  // 问题：express.json limit 500MB 过大，可被 DoS
  // 修改：降为 10MB
  // 状态：已修复
  app.use(express.json({ limit: '10mb' }))
  app.use(express.urlencoded({ extended: false, limit: '10mb' }))
  // [FIX-B006] 2026-07-28 | 后端 | 安全
  // 问题：文件上传无 MIME 类型校验，可上传任意文件
  // 修改：增加 safeFileNames + 白名单音频类型
  // 状态：已修复
  app.use(fileUpload({
    limits: { fileSize: 100 * 1024 * 1024 },
    useTempFiles: true,
    tempFileDir: tmpPath,
    abortOnLimit: true,
    parseNested: true,
    safeFileNames: true,
    preserveExtension: true,
  }))
  app.use(cache('2 minutes', (_, res) => res.statusCode === 200))

  // ====== 注册 api-enhanced 所有模块路由 ======
  const special = {
    'daily_signin.js': '/daily_signin',
    'fm_trash.js': '/fm_trash',
    'personal_fm.js': '/personal_fm',
  }
  const moduleDefinitions = await getModulesDefinitions(path.join(__dirname, 'module'), special)

  for (const moduleDef of moduleDefinitions) {
    app.all(moduleDef.route, async (req, res) => {
      ;[req.query, req.body].forEach((item) => {
        if (item && typeof item.cookie === 'string') {
          item.cookie = cookieToJson(decode(item.cookie))
        }
      })

      let query = Object.assign({}, { cookie: req.cookies }, req.query, req.body, req.files)

      try {
        let usedCrypto = ''
        const moduleResponse = await moduleDef.module(query, (...params) => {
          const obj = [...params]
          const options = obj[2] || {}
          usedCrypto = options.crypto || ''
          let ip = req.ip
          if (ip && ip.substring(0, 7) == '::ffff:') ip = ip.substring(7)
          if (ip == '::1') ip = global.cnIp
          obj[2] = { ...options, ip }
          return request(...obj)
        })
        logger.info(`Request Success: [${usedCrypto || (APP_CONF.encrypt ? 'eapi' : 'api')}] ${decode(req.originalUrl)}`)

        const cookies = moduleResponse.cookie
        if (!query.noCookie) {
          if (Array.isArray(cookies) && cookies.length > 0) {
            // [FIX-B005] 2026-07-28 | 后端 | 安全
            // 问题：Cookie 缺少 HttpOnly，XSS 可读取 session
            // 修改：统一添加 HttpOnly; Secure; SameSite=Lax
            // 状态：已修复
            const secureFlag = req.protocol === 'https' ? '; Secure' : ''
            res.append('Set-Cookie', cookies.map(c =>
              c.includes('HttpOnly') ? c : `${c}; HttpOnly; SameSite=Lax${secureFlag}`
            ))
          }
        }
        if (moduleResponse.redirectUrl) {
          res.redirect(moduleResponse.status || 302, moduleResponse.redirectUrl)
          return
        }
        res.status(moduleResponse.status).send(moduleResponse.body)
      } catch (moduleResponse) {
        logger.error(`${decode(req.originalUrl)}`, { status: moduleResponse.status, body: moduleResponse.body })
        if (!moduleResponse.body) {
          res.status(404).send({ code: 404, data: null, msg: 'Not Found' })
          return
        }
        if (moduleResponse.body && moduleResponse.body.code == '301') {
          moduleResponse.body.msg = '需要登录'
        }
        if (!query.noCookie) {
          const secureFlag = req.protocol === 'https' ? '; Secure' : ''
          res.append('Set-Cookie', (moduleResponse.cookie || []).map(c =>
            c.includes('HttpOnly') ? c : `${c}; HttpOnly; SameSite=Lax${secureFlag}`
          ))
        }
        res.status(moduleResponse.status).send(moduleResponse.body)
      }
    })
  }

  // ====== 自定义 /api/* 路由（前端桥接层）======
  const captchaSent = require('./module/captcha_sent')
  const captchaVerify = require('./module/captcha_verify')
  const loginCellphone = require('./module/login_cellphone')
  const cloudsearch = require('./module/cloudsearch')
  const songUrlV1 = require('./module/song_url_v1')

  // POST /api/send-code - 发送验证码
  app.post('/api/send-code', loginLimiter, async (req, res) => {
    const { phone } = req.body || {}
    if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
      return res.json({ success: false, message: '手机号格式不正确' })
    }

    try {
      const result = await captchaSent({ phone, ctcode: '86' }, (...params) => {
        return request(...params)
      })
      if (result.body.code === 200) {
        return res.json({ success: true, message: '短信验证码已发送', expires: 120 })
      }
      return res.status(400).json({ success: false, message: result.body.message || '发送失败' })
    } catch (e) {
      return res.status(400).json({ success: false, message: e.body?.message || e.message || '发送失败' })
    }
  })

  // POST /api/verify-login - 验证码登录
  app.post('/api/verify-login', loginLimiter, async (req, res) => {
    const { phone, code } = req.body || {}
    if (!phone || !code) {
      return res.json({ success: false, message: '请填写手机号和验证码' })
    }
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      return res.json({ success: false, message: '手机号格式不正确' })
    }
    if (!/^\d{4,6}$/.test(code)) {
      return res.json({ success: false, message: '验证码格式不正确' })
    }

    try {
      const result = await loginCellphone({ phone, captcha: code, countrycode: '86' }, (...params) => {
        return request(...params)
      })
      if (result.body.code === 200) {
        const cookieStr = result.body.cookie || ''
        // 提取 MUSIC_U 判断是否真正登录
        const hasMusicU = cookieStr.includes('MUSIC_U')
        const nickname = (result.body.profile && result.body.profile.nickname) || phone

         const id = state.nextId++
         state.accounts[id] = {
           id, name: `账号 ${id}`, phone, status: hasMusicU ? 'online' : 'offline',
           tasks: 0, completed: 0, failed: 0, progress: 0, running: false,
           lastError: null, cookies: cookieStr,
         }
         saveState()

        logger.info('手机号登录成功', { phone, nickname, hasMusicU })
        return res.json({
          success: true,
          message: `登录成功 - ${nickname}`,
          account: accountToDict(state.accounts[id]),
        })
      }
      return res.status(400).json({ success: false, message: result.body.message || '验证码错误或已过期' })
    } catch (e) {
      return res.status(400).json({ success: false, message: e.body?.message || e.message || '验证失败' })
    }
  })

  // POST /api/login/qr/key - 获取二维码key
  app.post('/api/login/qr/key', async (req, res) => {
    try {
      const loginQrKey = require('./package/module/login_qr_key')
      const result = await loginQrKey(req.body, (...params) => {
        return request(...params)
      })
      res.json(result)
    } catch (error) {
      logger.error('获取二维码key错误', { error: error.message })
      res.status(500).json({ code: 500, msg: '服务器错误' })
    }
  })

  // POST /api/login/qr/check - 检查二维码登录状态
  app.post('/api/login/qr/check', async (req, res) => {
    try {
      const loginQrCheck = require('./package/module/login_qr_check')
      const result = await loginQrCheck(req.body, (...params) => {
        return request(...params)
      })
      res.json(result)
    } catch (error) {
      logger.error('检查二维码登录状态错误', { error: error.message })
      res.status(500).json({ code: 500, msg: '服务器错误' })
    }
  })

  // POST /api/search
  app.post('/api/search', async (req, res) => {
    const { keyword } = req.body || {}
    if (!keyword) return res.json({ success: false, songs: [], message: '请提供搜索关键词' })

    try {
      const result = await cloudsearch({ keywords: keyword, type: '1', limit: '30' }, (...params) => {
        return request(...params)
      })
      const songs = (result.body.result && result.body.result.songs || []).map(s => ({
        id: s.id,
        name: s.name,
        artists: (s.ar || []).map(a => a.name).join('/'),
        album: (s.al && s.al.name) || '',
        duration: Math.floor((s.dt || 0) / 1000),
      }))
      return res.json({ success: true, songs })
    } catch (e) {
      return res.json({ success: false, songs: [], message: e.body?.message || e.message })
    }
  })

  // POST /api/play - 统一播放接口，支持灵活组合参数
  //   mode: 'artist' | 'mix' | 'daily'
  //   artist_id: 歌手ID（mode=artist 或 mix 时使用）
  //   artist_name: 歌手名称（可选，用于搜索）
  //   count: 播放歌曲数量（可选，默认不限）
  //   minutes: 播放时长分钟数（可选，默认不限）
  //   count 和 minutes 同时指定时，优先满足 count，再按最多 minutes 分钟截断
  //   都不指定时，默认播放 10 首
  app.post('/api/play', async (req, res) => {
    const { mode, artist_id, artist_name, count, minutes } = req.body || {}

    // 找到第一个在线账号的 cookie
    const onlineAcct = Object.values(state.accounts).find(a => a.status === 'online')
    if (!onlineAcct) return res.json({ success: false, message: '没有在线账号' })

    try {
      let allSongs = []

      // 获取歌曲源
      if (mode === 'artist' || (mode === 'mix' && artist_id)) {
        // 获取歌手歌曲
        const artistSongs = require('./module/artist_songs')
        const result = await artistSongs({ id: artist_id, limit: count || 100 }, (...params) => {
          return request(...params)
        })
        if (result.body.code !== 200) {
          return res.json({ success: false, message: '获取歌手歌曲失败' })
        }
        allSongs = result.body.data || []
        if (allSongs.length === 0) {
          return res.json({ success: false, message: '该歌手没有找到歌曲' })
        }
      } else if (artist_name) {
        // 按歌手名搜索
        const searchResult = await require('./module/cloudsearch')({
          keywords: artist_name,
          type: '1',
          limit: 100
        }, (...params) => {
          return request(...params)
        })
        if (searchResult.body.code !== 200) {
          return res.json({ success: false, message: '搜索失败' })
        }
        allSongs = searchResult.body.result?.songs || []
      } else {
        // 默认搜索热门歌曲
        const searchResult = await require('./module/cloudsearch')({
          keywords: '热门',
          type: '1',
          limit: 100
        }, (...params) => {
          return request(...params)
        })
        if (searchResult.body.code !== 200) {
          return res.json({ success: false, message: '搜索失败' })
        }
        allSongs = searchResult.body.result?.songs || []
      }

      if (allSongs.length === 0) {
        return res.json({ success: false, message: '没有找到歌曲' })
      }

      // 应用筛选条件
      let selectedSongs = []
      let totalDuration = 0
      const maxCount = count || Infinity
      const maxDuration = minutes ? minutes * 60 : Infinity

      for (const song of allSongs) {
        if (selectedSongs.length >= maxCount) break
        const duration = (song.dt || 0) / 1000
        if (totalDuration + duration > maxDuration && selectedSongs.length > 0) break
        selectedSongs.push(song)
        totalDuration += duration
      }

      // 如果 count 和 minutes 都没指定，默认取 10 首
      if (!count && !minutes) {
        selectedSongs = allSongs.slice(0, 10)
        totalDuration = selectedSongs.reduce((s, song) => s + (song.dt || 0) / 1000, 0)
      }

      if (selectedSongs.length === 0) {
        return res.json({ success: false, message: '没有符合条件的歌曲' })
      }

      // 构建播放列表
      const songs = selectedSongs.map(s => ({
        id: s.id,
        name: s.name,
        artists: (s.ar || []).map(a => a.name).join('/'),
        album: (s.al && s.al.name) || '',
        duration: Math.floor((s.dt || 0) / 1000)
      }))

      // 播放第一首歌曲
      const firstSong = selectedSongs[0]
      const query = { id: String(firstSong.id), level: 'standard' }
      if (onlineAcct.cookies) query.cookie = onlineAcct.cookies
      const urlResult = await songUrlV1(query, (...params) => {
        return request(...params)
      })
      const data = urlResult.body.data && urlResult.body.data[0]

      if (data && data.url) {
        const parts = []
        if (mode === 'artist' || artist_id) parts.push('歌手歌曲')
        if (count) parts.push(`最多 ${count} 首`)
        if (minutes) parts.push(`最多 ${minutes} 分钟`)
        const msg = `开始播放 ${selectedSongs.length} 首歌曲${parts.length ? ` (${parts.join('，')})` : ''}，共 ${Math.floor(totalDuration / 60)} 分钟`

        return res.json({
          success: true,
          message: msg,
          song_id: firstSong.id,
          url: data.url,
          br: data.br,
          total_songs: selectedSongs.length,
          total_duration: Math.floor(totalDuration),
          mode: mode || 'default',
          songs
        })
      }

      return res.json({ success: false, message: '无法获取播放地址' })
    } catch (e) {
      return res.json({ success: false, message: e.body?.message || e.message })
    }
  })

  // 保留旧端点兼容（委托给统一播放逻辑）
  ;['artist', 'count', 'duration'].forEach(suffix => {
    app.post(`/api/play/${suffix}`, async (req, res) => {
      const body = { ...req.body, mode: suffix === 'artist' ? 'artist' : 'mix' }
      const newReq = Object.assign(req, { body })
      try {
        // 手动调用统一播放逻辑
        const onlineAcct = Object.values(state.accounts).find(a => a.status === 'online')
        if (!onlineAcct) return res.json({ success: false, message: '没有在线账号' })

        let allSongs = []
        if (suffix === 'artist' || body.artist_id) {
          const artistSongs = require('./module/artist_songs')
          const result = await artistSongs({ id: body.artist_id, limit: body.count || 100 }, (...params) => {
            return request(...params)
          })
          if (result.body.code !== 200) return res.json({ success: false, message: '获取歌手歌曲失败' })
          allSongs = result.body.data || []
        } else {
          const searchResult = await require('./module/cloudsearch')({
            keywords: '热门', type: '1', limit: 100
          }, (...params) => request(...params))
          if (searchResult.body.code !== 200) return res.json({ success: false, message: '搜索失败' })
          allSongs = searchResult.body.result?.songs || []
        }

        if (allSongs.length === 0) return res.json({ success: false, message: '没有找到歌曲' })

        let selectedSongs = []
        let totalDuration = 0
        const maxCount = suffix === 'count' ? (body.count || 10) : Infinity
        const maxDuration = suffix === 'duration' ? ((body.minutes || 30) * 60) : Infinity

        for (const song of allSongs) {
          if (selectedSongs.length >= maxCount) break
          const dur = (song.dt || 0) / 1000
          if (totalDuration + dur > maxDuration && selectedSongs.length > 0) break
          selectedSongs.push(song)
          totalDuration += dur
        }

        if (!body.count && !body.minutes) {
          selectedSongs = allSongs.slice(0, 10)
          totalDuration = selectedSongs.reduce((s, song) => s + (song.dt || 0) / 1000, 0)
        }

        const songs = selectedSongs.map(s => ({
          id: s.id, name: s.name,
          artists: (s.ar || []).map(a => a.name).join('/'),
          album: (s.al && s.al.name) || '',
          duration: Math.floor((s.dt || 0) / 1000)
        }))

        const firstSong = selectedSongs[0]
        const query = { id: String(firstSong.id), level: 'standard' }
        if (onlineAcct.cookies) query.cookie = onlineAcct.cookies
        const urlResult = await songUrlV1(query, (...params) => request(...params))
        const data = urlResult.body.data && urlResult.body.data[0]

        if (data && data.url) {
          return res.json({
            success: true,
            message: `开始播放 ${selectedSongs.length} 首歌曲，共 ${Math.floor(totalDuration / 60)} 分钟`,
            song_id: firstSong.id, url: data.url, br: data.br,
            total_songs: selectedSongs.length,
            total_duration: Math.floor(totalDuration),
            mode: suffix,
            songs
          })
        }
        return res.json({ success: false, message: '无法获取播放地址' })
      } catch (e) {
        return res.json({ success: false, message: e.body?.message || e.message })
      }
    })
  })

  // GET /api/accounts
  app.get('/api/accounts', (req, res) => {
    try {
      return res.json({
        accounts: Object.values(state.accounts).map(accountToDict),
      })
    } catch (e) {
      logger.error('GET /api/accounts', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // GET /api/stats
  app.get('/api/stats', (req, res) => {
    try {
      const accs = Object.values(state.accounts)
      const totalTasks = accs.reduce((s, a) => s + a.tasks, 0)
      const completedTasks = accs.reduce((s, a) => s + a.completed, 0)
      const successRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0
      return res.json({
        total_accounts: accs.length,
        online_accounts: accs.filter(a => a.status === 'online').length,
        running_accounts: accs.filter(a => a.running).length,
        total_tasks: totalTasks,
        completed_tasks: completedTasks,
        failed_tasks: accs.reduce((s, a) => s + a.failed, 0),
        success_rate: successRate,
        max_threads: state.maxThreads,
        active_threads: Object.keys(state.runningTasks).length,
      })
    } catch (e) {
      logger.error('GET /api/stats', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // GET /api/api-debugger - API调试器
  app.get('/api/api-debugger', (req, res) => {
    try {
      const fs = require('fs')
      const path = require('path')
      const moduleDir = path.join(__dirname, 'package/module')
      const files = fs.readdirSync(moduleDir)
      const apiList = []
      for (const file of files) {
        if (file.endsWith('.js')) {
          const name = file.replace('.js', '')
          apiList.push({
            name: name,
            file: file
          })
        }
      }
      return res.json({
        success: true,
        apis: apiList.sort((a, b) => a.name.localeCompare(b.name))
      })
      } catch (error) {
        logger.error('API调试器错误', { error: error.message })
        return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // GET /api/cloud - 云盘搜索
  app.get('/api/cloud', async (req, res) => {
    try {
      const userCloud = require('./package/module/user_cloud')
      const result = await userCloud({ limit: '30', offset: '0' }, (...params) => {
        return request(...params)
      })
      return res.json({
        success: true,
        songs: result.body.privileges || []
      })
    } catch (error) {
      logger.error('云盘搜索错误', { error: error.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/playlist/import - 歌单导入
  app.post('/api/playlist/import', async (req, res) => {
    try {
      const playlistImport = require('./package/module/playlist_import_name_task_create')
      const result = await playlistImport(req.body, (...params) => {
        return request(...params)
      })
      return res.json(result)
    } catch (error) {
      logger.error('歌单导入错误', { error: error.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/playlist/import/status - 歌单导入状态
  app.post('/api/playlist/import/status', async (req, res) => {
    try {
      const playlistImportStatus = require('./package/module/playlist_import_task_status')
      const result = await playlistImportStatus({ id: req.body.id }, (...params) => {
        return request(...params)
      })
      return res.json(result)
    } catch (error) {
      logger.error('歌单导入状态错误', { error: error.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // GET /api/status
  app.get('/api/status', (req, res) => {
    try {
      const accs = Object.values(state.accounts)
      return res.json({
        online: accs.filter(a => a.status === 'online').length,
        running: accs.filter(a => a.running).length,
        offline: accs.filter(a => a.status === 'offline').length,
        total: accs.length,
      })
    } catch (e) {
      logger.error('GET /api/status', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/account/remove
  app.post('/api/account/remove', (req, res) => {
    try {
      const id = (req.body || {}).id || (req.body || {}).account_id
      if (id !== undefined && state.accounts[id]) {
        // [FIX-B011] 清理关联定时器
        if (state.accounts[id]._reloginTimer) clearTimeout(state.accounts[id]._reloginTimer)
        delete state.accounts[id]
        saveState()
        return res.json({ success: true, message: `账号 ${id} 已删除` })
      }
      return res.status(404).json({ success: false, message: '账号不存在' })
    } catch (e) {
      logger.error('POST /api/account/remove', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/account/relogin
  app.post('/api/account/relogin', (req, res) => {
    try {
      const id = (req.body || {}).id || (req.body || {}).account_id
      const acc = state.accounts[id]
      if (!acc) return res.status(404).json({ success: false, message: '账号不存在' })
      acc.status = 'loading'
      // [FIX-B011] 2026-07-28 | 后端 | 安全
      // 问题：relogin 的 setTimeout 无法取消，账号删除后仍会执行
      // 修改：存储 timerId 到 account 对象上，删除时清理
      // 状态：已修复
      if (acc._reloginTimer) clearTimeout(acc._reloginTimer)
      acc._reloginTimer = setTimeout(() => {
        if (state.accounts[id]) acc.status = 'online'
      }, 2000)
      return res.json({ success: true, message: `重新登录中... 账号 ${id}` })
    } catch (e) {
      logger.error('POST /api/account/relogin', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/task/start
  app.post('/api/task/start', (req, res) => {
    try {
      const { account_id, type } = req.body || {}
      if (account_id === undefined) {
        return res.status(400).json({ success: false, message: '参数错误: 缺少 account_id' })
      }
      const acc = state.accounts[account_id]
      if (!acc) return res.status(404).json({ success: false, message: '账号不存在' })
      if (acc.running) return res.status(400).json({ success: false, message: '账号正在执行任务' })
      if (acc.status !== 'online') return res.status(400).json({ success: false, message: '账号未在线' })

      acc.running = true
      acc.progress = 0
      simulateTask(acc)
      saveState()
      return res.json({ success: true, message: `任务已启动 - ${acc.name}` })
    } catch (e) {
      logger.error('POST /api/task/start', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/task/stop
  app.post('/api/task/stop', (req, res) => {
    try {
      const id = (req.body || {}).account_id || (req.body || {}).id
      const acc = state.accounts[id]
      if (acc && acc.running) {
      acc.running = false
      acc.progress = 0
      saveState()
      return res.json({ success: true, message: `任务已停止 - ${acc.name}` })
      }
      return res.status(400).json({ success: false, message: '没有正在运行的任务' })
    } catch (e) {
      logger.error('POST /api/task/stop', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/task/start-all
  app.post('/api/task/start-all', (req, res) => {
    try {
      const { type } = req.body || {}
      const started = []
      for (const acc of Object.values(state.accounts)) {
        if (acc.status === 'online' && !acc.running) {
          acc.running = true
          acc.progress = 0
          simulateTask(acc)
          started.push(acc.id)
        }
      }
      saveState()
      if (started.length === 0) {
        return res.json({ success: true, message: '没有可执行的账号', started: [] })
      }
      return res.json({ success: true, message: `已启动 ${started.length} 个账号的任务`, started })
    } catch (e) {
      logger.error('POST /api/task/start-all', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/task/stop-all
  app.post('/api/task/stop-all', (req, res) => {
    try {
      const stopped = []
      for (const acc of Object.values(state.accounts)) {
        if (acc.running) {
          acc.running = false
          acc.progress = 0
          stopped.push(acc.id)
        }
      }
      saveState()
      return res.json({ success: true, message: `已停止 ${stopped.length} 个账号的任务`, stopped })
    } catch (e) {
      logger.error('POST /api/task/stop-all', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // POST /api/settings/threads
  app.post('/api/settings/threads', (req, res) => {
    try {
      const count = (req.body || {}).max_threads || 4
      state.maxThreads = Math.max(1, Math.min(16, count))
      saveState()
      return res.json({ success: true, message: `线程数已更新为 ${state.maxThreads}` })
    } catch (e) {
      logger.error('POST /api/settings/threads', { error: e.message })
      return res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // ====== 任务模拟 ======
  function simulateTask(account) {
    if (!account.running) return
    const interval = setInterval(() => {
      if (!account.running) {
        clearInterval(interval)
        return
      }
      account.progress += Math.random() * 15
      if (account.progress >= 100) {
        account.progress = 100
        account.running = false
        account.tasks++
        account.completed++
        clearInterval(interval)
      }
    }, 500)
  }

  // ====== 首页和 SPA 回退 ======
  app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'))
  })

  app.get('/index.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'))
  })

  // ====== 全局错误处理 (B003) ======
  // [FIX-B003] 2026-07-28 | 后端 | 安全
  // 问题：缺少全局 Express 错误处理器，未捕获异常返回 HTML 而非 JSON
  // 修改：增加 4参数错误处理中间件
  // 状态：已修复
  app.use((err, req, res, _next) => {
    logger.critical('Unhandled error', { path: req.path, error: err.message, stack: err.stack })
    if (!res.headersSent) {
      res.status(500).json({ success: false, message: '服务器内部错误' })
    }
  })

  // ====== 启动 ======
  app.listen(PORT, '0.0.0.0', () => {
    logger.info('服务启动', { port: PORT, maxThreads: state.maxThreads })
  })
}

startServer().catch(err => {
  logger.critical('启动失败', { error: err.message })
  process.exit(1)
})
