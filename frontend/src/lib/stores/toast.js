import { writable } from 'svelte/store'

export const toasts = writable([])

export function showToast(message, type = 'success', duration) {
  const defaultDuration = type === 'error' ? 5000 : type === 'warning' ? 0 : 3000
  const finalDuration = duration !== undefined ? duration : defaultDuration

  const id = crypto.randomUUID()
  toasts.update((list) => {
    const next = [...list, { id, message, type }]
    return next.length > 3 ? next.slice(next.length - 3) : next
  })

  if (finalDuration > 0) {
    setTimeout(() => dismissToast(id), finalDuration)
  }

  return id
}

export function dismissToast(id) {
  toasts.update((list) => list.filter((t) => t.id !== id))
}
