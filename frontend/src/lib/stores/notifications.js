import { writable } from 'svelte/store'
import { getNotifications } from '../api/notifications.js'

export const unreadCount = writable(0)
export const notifications = writable([])

let _pollInterval = null
let _lastKnownCount = 0

/**
 * Fetch notifications from the server and update the store.
 * @param {number} page
 * @returns {Promise<Object|null>} paginated response or null on error
 */
export async function fetchNotifications(page = 1) {
  try {
    const data = await getNotifications({ page, size: 20 })
    notifications.set(data.items || [])
    return data
  } catch {
    // Silently fail during background polling
    return null
  }
}

/**
 * Reset unread count to 0 (call when dropdown is opened).
 */
export function resetUnreadCount() {
  unreadCount.set(0)
}

/**
 * Start polling notifications every 30 seconds.
 * Safe to call multiple times — only one interval is created.
 */
export async function pollNotifications() {
  if (_pollInterval) return // already polling

  // Initial fetch — set unreadCount based on SENT items
  const data = await fetchNotifications()
  if (data) {
    const sentCount = (data.items || []).filter((n) => n.status === 'SENT').length
    unreadCount.set(sentCount)
    _lastKnownCount = sentCount
  }

  // Poll every 30 seconds
  _pollInterval = setInterval(async () => {
    const data = await fetchNotifications()
    if (data) {
      const newSentCount = (data.items || []).filter((n) => n.status === 'SENT').length
      // Add newly arrived SENT notifications to unread count
      const diff = newSentCount - _lastKnownCount
      if (diff > 0) {
        unreadCount.update((n) => n + diff)
      }
      _lastKnownCount = newSentCount
    }
  }, 30000)
}

/**
 * Stop the polling interval (call on app unmount or logout).
 */
export function stopPolling() {
  if (_pollInterval) {
    clearInterval(_pollInterval)
    _pollInterval = null
    _lastKnownCount = 0
  }
}
