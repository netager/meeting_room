import { get, post, del } from './client.js'

export async function runSync() {
  return post('/admin/sync/run', {})
}

export async function getAuditLogs(params = {}) {
  const qs = new URLSearchParams()
  if (params.action) qs.set('action', params.action)
  if (params.resource_type) qs.set('resource_type', params.resource_type)
  if (params.actor_emp_no) qs.set('actor_emp_no', params.actor_emp_no)
  if (params.date_from) qs.set('date_from', params.date_from)
  if (params.date_to) qs.set('date_to', params.date_to)
  if (params.page) qs.set('page', params.page)
  if (params.size) qs.set('size', params.size)
  const query = qs.toString()
  return get(`/admin/audit-logs${query ? '?' + query : ''}`)
}

export async function getAuditLog(logId) {
  return get(`/admin/audit-logs/${logId}`)
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
