import { get, post, put, del } from './client.js'

export async function listRooms(params = {}) {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  const qs = query.toString()
  return get(`/meeting-rooms${qs ? '?' + qs : ''}`)
}

export async function getRoom(roomId) {
  return get(`/meeting-rooms/${roomId}`)
}

export async function createRoom(data) {
  return post('/meeting-rooms', data)
}

export async function updateRoom(roomId, data) {
  return put(`/meeting-rooms/${roomId}`, data)
}

export async function deleteRoom(roomId) {
  return del(`/meeting-rooms/${roomId}`)
}

export async function getRoomSchedule(roomId, date) {
  return get(`/meeting-rooms/${roomId}/schedule?date=${date}`)
}

export async function createEquipment(roomId, data) {
  return post(`/meeting-rooms/${roomId}/equipment`, data)
}

export async function updateEquipment(roomId, eqId, data) {
  return put(`/meeting-rooms/${roomId}/equipment/${eqId}`, data)
}

export async function deleteEquipment(roomId, eqId) {
  return del(`/meeting-rooms/${roomId}/equipment/${eqId}`)
}
