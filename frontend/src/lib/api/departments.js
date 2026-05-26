import { get, post, put, del } from './client.js'

export async function listDepartments(includeInactive = false) {
  return get(`/departments${includeInactive ? '?include_inactive=true' : ''}`)
}

export async function createDepartment(data) {
  return post('/departments', data)
}

export async function updateDepartment(code, data) {
  return put(`/departments/${code}`, data)
}

export async function deleteDepartment(code) {
  return del(`/departments/${code}`)
}

export async function listTeams(deptCode) {
  return get(`/departments/${deptCode}/teams`)
}

export async function createTeam(data) {
  return post('/teams', data)
}

export async function updateTeam(code, data) {
  return put(`/teams/${code}`, data)
}

export async function deleteTeam(code) {
  return del(`/teams/${code}`)
}
