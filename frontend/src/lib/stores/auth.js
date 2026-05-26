import { writable, derived } from 'svelte/store'
import { setAccessToken, clearAccessToken } from '../api/client.js'
import { refreshToken } from '../api/auth.js'

function decodeJwtPayload(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}

export const currentUser = writable(null)
export const isAuthenticated = derived(currentUser, ($u) => $u !== null)
export const isInitialPassword = derived(currentUser, ($u) => $u?.is_initial_password ?? false)

export function setUserFromToken(accessToken, overrides = {}) {
  const payload = decodeJwtPayload(accessToken)
  if (!payload) return

  setAccessToken(accessToken)
  currentUser.set({
    emp_no: payload.sub,
    name: payload.name || payload.sub,
    is_admin: payload.is_admin || false,
    is_room_manager: payload.is_room_manager || false,
    is_initial_password: overrides.is_initial_password ?? payload.is_initial_password ?? false,
  })
}

export async function initAuth() {
  try {
    const data = await refreshToken()
    setUserFromToken(data.access_token)
  } catch {
    clearAccessToken()
    currentUser.set(null)
  }
}

export function clearAuth() {
  clearAccessToken()
  currentUser.set(null)
}
