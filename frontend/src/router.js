import { writable } from 'svelte/store'
import { get } from 'svelte/store'
import { isAuthenticated, isInitialPassword, currentUser } from './lib/stores/auth.js'

const PUBLIC_ROUTES = new Set(['/login'])
const PASSWORD_CHANGE_ROUTE = '/password-change'
const ADMIN_ROUTES = new Set(['/admin'])

// Static routes checked before dynamic patterns
const STATIC_ROUTES = new Set([
  '/',
  '/login',
  '/password-change',
  '/meetings',
  '/meetings/new',
  '/rooms',
  '/room-management',
  '/admin',
])

// Dynamic route patterns — order matters (more specific first)
const DYNAMIC_PATTERNS = [
  { pattern: /^\/meetings\/([^/]+)\/edit$/, route: '/meetings/:id/edit', paramKeys: ['id'] },
  { pattern: /^\/meetings\/([^/]+)$/, route: '/meetings/:id', paramKeys: ['id'] },
]

function parseHash(hash) {
  if (!hash || hash === '#' || hash === '#/') return { path: '/', params: {} }
  const rawPath = hash.slice(1) // remove '#'

  if (STATIC_ROUTES.has(rawPath)) return { path: rawPath, params: {} }

  for (const def of DYNAMIC_PATTERNS) {
    const match = rawPath.match(def.pattern)
    if (match) {
      const params = {}
      def.paramKeys.forEach((key, i) => {
        params[key] = match[i + 1]
      })
      return { path: def.route, params }
    }
  }

  return { path: rawPath, params: {} }
}

function getHashParsed() {
  return parseHash(window.location.hash)
}

export const currentRoute = writable(getHashParsed().path)
export const routeParams = writable(getHashParsed().params)

export function navigateTo(path) {
  const hash = path.startsWith('#') ? path : '#' + path
  const event = new CustomEvent('before-navigate', {
    detail: { to: hash },
    cancelable: true,
  })
  if (!window.dispatchEvent(event)) return
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
    const parsed = getHashParsed()
    const guarded = guard(parsed.path)
    currentRoute.set(guarded)
    routeParams.set(guarded === parsed.path ? parsed.params : {})
  })
}

export function initRouter() {
  const parsed = getHashParsed()
  const guarded = guard(parsed.path)
  if (guarded !== parsed.path) {
    currentRoute.set(guarded)
    routeParams.set({})
  } else {
    currentRoute.set(parsed.path)
    routeParams.set(parsed.params)
  }
}
