import { get, put, del } from './client.js'

export async function listEmployees(params = {}) {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', params.page)
  if (params.size) qs.set('size', params.size)
  if (params.status) qs.set('status', params.status)
  if (params.search) qs.set('search', params.search)
  const query = qs.toString()
  return get(`/employees${query ? '?' + query : ''}`)
}

export async function searchEmployees(query) {
  return get(`/employees/search?q=${encodeURIComponent(query)}`)
}

export async function getEmployee(empNo) {
  return get(`/employees/${empNo}`)
}

export async function updateEmployee(empNo, data) {
  return put(`/employees/${empNo}`, data)
}

export async function retireEmployee(empNo) {
  return del(`/employees/${empNo}`)
}

export async function updatePermissions(empNo, data) {
  return put(`/admin/employees/${empNo}/permissions`, data)
}
