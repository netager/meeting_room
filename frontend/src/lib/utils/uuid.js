/**
 * UUID v4 생성 유틸리티
 * crypto.randomUUID()는 HTTPS 또는 localhost에서만 동작하므로
 * HTTP(비보안 컨텍스트)에서도 작동하는 폴백을 제공한다.
 */
export function generateUUID() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // 폴백: Math.random 기반 UUID v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
