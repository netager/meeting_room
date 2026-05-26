import { showToast } from '../stores/toast.js'

let _accessToken = null

export function getAccessToken() {
  return _accessToken
}

export function setAccessToken(token) {
  _accessToken = token
}

export function clearAccessToken() {
  _accessToken = null
}

export class ApiError extends Error {
  constructor(code, message, detail, status) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.detail = detail
    this.status = status
  }
}

let isRefreshing = false
let pendingRequests = []

async function _refreshAccessToken() {
  const res = await fetch('/api/auth/token/refresh', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-Request-ID': crypto.randomUUID() },
  })
  if (!res.ok) {
    throw new Error('Refresh failed')
  }
  const data = await res.json()
  return data.access_token
}

function _navigateTo(path) {
  window.location.hash = path.startsWith('#') ? path : '#' + path
}

function _onSessionExpired() {
  window.dispatchEvent(new CustomEvent('auth:session-expired'))
}

async function _parseErrorResponse(res) {
  try {
    const data = await res.json()
    return data.error || { code: 'UNKNOWN', message: res.statusText }
  } catch {
    return { code: 'UNKNOWN', message: res.statusText }
  }
}

export async function request(path, options = {}) {
  const headers = {
    'X-Request-ID': crypto.randomUUID(),
    ...options.headers,
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  if (_accessToken) {
    headers['Authorization'] = `Bearer ${_accessToken}`
  }

  const res = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  if (res.status === 401) {
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push({ resolve, reject, path, options })
      })
    }

    isRefreshing = true
    try {
      const newToken = await _refreshAccessToken()
      setAccessToken(newToken)
      const pending = [...pendingRequests]
      pendingRequests = []
      pending.forEach(({ resolve, path, options }) => resolve(request(path, options)))
      return request(path, options)
    } catch {
      const pending = [...pendingRequests]
      pendingRequests = []
      pending.forEach(({ reject }) => reject(new ApiError('TOKEN_EXPIRED', '세션이 만료되었습니다.', null, 401)))
      clearAccessToken()
      _onSessionExpired()
      _navigateTo('#/login')
      showToast('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.', 'error')
      throw new ApiError('TOKEN_EXPIRED', '세션이 만료되었습니다.', null, 401)
    } finally {
      isRefreshing = false
    }
  }

  if (!res.ok) {
    const err = await _parseErrorResponse(res)
    throw new ApiError(err.code, err.message, err.detail, res.status)
  }

  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return res.json()
  }
  return res
}

export async function get(path, options = {}) {
  return request(path, { method: 'GET', ...options })
}

export async function post(path, body, options = {}) {
  return request(path, {
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body),
    ...options,
  })
}

export async function put(path, body, options = {}) {
  return request(path, {
    method: 'PUT',
    body: JSON.stringify(body),
    ...options,
  })
}

export async function patch(path, body, options = {}) {
  return request(path, {
    method: 'PATCH',
    body: JSON.stringify(body),
    ...options,
  })
}

export async function del(path, options = {}) {
  return request(path, { method: 'DELETE', ...options })
}
