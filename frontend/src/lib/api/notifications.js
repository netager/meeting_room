import { get } from './client.js'

/**
 * Get the current user's notifications (paginated, newest first).
 * @param {Object} params - { page, size }
 */
export async function getNotifications(params = {}) {
  const searchParams = new URLSearchParams()
  if (params.page) searchParams.set('page', String(params.page))
  if (params.size) searchParams.set('size', String(params.size))
  const query = searchParams.toString()
  return get(`/notifications${query ? '?' + query : ''}`)
}
