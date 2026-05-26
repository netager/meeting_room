import { ApiError, post } from './client.js'

export async function login(username, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': crypto.randomUUID(),
    },
    body: JSON.stringify({ username, password }),
    credentials: 'include',
  })

  if (!res.ok) {
    let errData
    try {
      errData = await res.json()
    } catch {
      errData = { error: { code: 'UNKNOWN', message: res.statusText } }
    }
    const err = errData.error || { code: 'UNKNOWN', message: res.statusText }
    const apiErr = new ApiError(err.code, err.message, err.detail, res.status)
    if (res.status === 423) {
      apiErr.unlockAt = res.headers.get('X-Unlock-At')
    }
    throw apiErr
  }

  return res.json()
}

export async function logout() {
  return post('/auth/logout', {})
}

export async function refreshToken() {
  const res = await fetch('/api/auth/token/refresh', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-Request-ID': crypto.randomUUID() },
  })
  if (!res.ok) {
    throw new Error('Refresh failed')
  }
  return res.json()
}

export async function changePassword(currentPassword, newPassword) {
  return post('/auth/password/change', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
