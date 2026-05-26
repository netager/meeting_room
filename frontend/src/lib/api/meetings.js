import { get, post, put, del, request, getAccessToken } from './client.js'

export async function listMeetings(params = {}) {
  const qs = new URLSearchParams()
  if (params.my) qs.set('my', 'true')
  if (params.status) qs.set('status', params.status)
  if (params.date_from) qs.set('date_from', params.date_from)
  if (params.date_to) qs.set('date_to', params.date_to)
  if (params.room_id) qs.set('room_id', params.room_id)
  if (params.page) qs.set('page', String(params.page))
  if (params.size) qs.set('size', String(params.size))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return get(`/meetings${query}`)
}

export async function getMyMeetings(params = {}) {
  return listMeetings({ ...params, my: true })
}

export async function getMeeting(meetingId) {
  return get(`/meetings/${meetingId}`)
}

export async function createMeeting(data) {
  return post('/meetings', data)
}

export async function updateMeeting(meetingId, data) {
  return put(`/meetings/${meetingId}`, data)
}

export async function cancelMeeting(meetingId) {
  return del(`/meetings/${meetingId}`)
}

export async function completeMeeting(meetingId) {
  return post(`/meetings/${meetingId}/complete`, {})
}

export async function getFiles(meetingId) {
  return get(`/meetings/${meetingId}/files`)
}

export async function downloadFile(meetingId, fileId) {
  // Use request() for auth header, get Blob, trigger download via <a>
  const res = await request(`/meetings/${meetingId}/files/${fileId}`, { method: 'GET' })
  const blob = await res.blob()
  const contentDisposition = res.headers.get('content-disposition') || ''
  let filename = 'download'
  const rfc5987 = contentDisposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i)
  const plain = contentDisposition.match(/filename="(.+?)"/i)
  if (rfc5987) filename = decodeURIComponent(rfc5987[1])
  else if (plain) filename = plain[1]
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function deleteFile(meetingId, fileId) {
  return del(`/meetings/${meetingId}/files/${fileId}`)
}

export async function addAttendee(meetingId, empNo) {
  return post(`/meetings/${meetingId}/attendees`, { emp_no: empNo })
}

export async function removeAttendee(meetingId, empNo) {
  return del(`/meetings/${meetingId}/attendees/${empNo}`)
}

export function uploadFile(meetingId, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) } catch { resolve({}) }
      } else {
        try {
          const data = JSON.parse(xhr.responseText)
          reject(new Error(data?.error?.message || '업로드 실패'))
        } catch {
          reject(new Error('업로드 실패'))
        }
      }
    })
    xhr.addEventListener('error', () => reject(new Error('네트워크 오류로 업로드 실패')))
    xhr.open('POST', `/api/meetings/${meetingId}/files`)
    const token = getAccessToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}
