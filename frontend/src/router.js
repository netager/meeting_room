import { writable } from 'svelte/store'
import { get } from 'svelte/store'
import { isAuthenticated, isInitialPassword, currentUser } from './lib/stores/auth.js'

const PUBLIC_ROUTES = new Set(['/login'])
const PASSWORD_CHANGE_ROUTE = '/password-change'
const ADMIN_ROUTES = new Set(['/admin'])

function getHashRoute() {
  const hash = window.location.hash
  if (!hash || hash === '#' || hash === '#/') return '/'
  return hash.slice(1) // remove '#'
}

export const currentRoute = writable(getHashRoute())

export function navigateTo(path) {
  const hash = path.startsWith('#') ? path : '#' + path
  window.location.hash = hash
}

function guard(path) {
  const authed = get(isAuthenticated)
  const needsPasswordChange = get(isInitialPassword)
  const user = get(currentUser)

  if (!authed && !PUBLIC_ROUTES.has(path)) {
    navigateTo('#/login')
    return '/login'
  }

  if (authed && needsPasswordChange && path !== PASSWORD_CHANGE_ROUTE) {
    navigateTo('#' + PASSWORD_CHANGE_ROUTE)
    return PASSWORD_CHANGE_ROUTE
  }

  if (authed && path === '/login') {
    navigateTo('#/')
    return '/'
  }

  if (authed && ADMIN_ROUTES.has(path) && !user?.is_admin) {
    navigateTo('#/')
    return '/'
  }

  return path
}

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    const raw = getHashRoute()
    const guarded = guard(raw)
    currentRoute.set(guarded)
  })
}

export function initRouter() {
  const raw = getHashRoute()
  const guarded = guard(raw)
  if (guarded !== raw) {
    currentRoute.set(guarded)
  } else {
    currentRoute.set(raw)
  }
}
