import { get, post, del } from './client.js'

export async function runSync() {
  return post('/admin/sync/run', {})
}

export async function getAuditLogs(params = {}) {
  const qs = new URLSearchParams()
  if (params.action) qs.set('action', params.action)
  if (params.limit) qs.set('limit', params.limit)
  const query = qs.toString()
  return get(`/admin/audit-logs${query ? '?' + query : ''}`)
}

export async function listStaging() {
  return get('/admin/staging')
}

export async function upsertStaging(record) {
  return post('/admin/staging', record)
}

export async function deleteStaging(empNo) {
  return del(`/admin/staging/${empNo}`)
}
