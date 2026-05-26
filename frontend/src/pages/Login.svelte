<script>
  import { login } from '../lib/api/auth.js'
  import { setUserFromToken } from '../lib/stores/auth.js'
  import { navigateTo } from '../router.js'

  let username = $state('')
  let password = $state('')
  let errorMessage = $state('')
  let submitting = $state(false)

  // Account lock state
  let lockedUntil = $state(null)
  let lockCountdown = $state('')
  let lockTimer = null

  function startCountdown(unlockAt) {
    lockedUntil = new Date(unlockAt)
    if (lockTimer) clearInterval(lockTimer)
    lockTimer = setInterval(() => {
      const diff = lockedUntil - new Date()
      if (diff <= 0) {
        lockCountdown = ''
        lockedUntil = null
        clearInterval(lockTimer)
        lockTimer = null
      } else {
        const totalSecs = Math.floor(diff / 1000)
        const mins = Math.floor(totalSecs / 60)
        const secs = totalSecs % 60
        lockCountdown = `${mins}분 ${secs.toString().padStart(2, '0')}초`
      }
    }, 1000)
    // Set immediately too
    const diff = lockedUntil - new Date()
    if (diff > 0) {
      const totalSecs = Math.floor(diff / 1000)
      lockCountdown = `${Math.floor(totalSecs / 60)}분 ${(totalSecs % 60).toString().padStart(2, '0')}초`
    }
  }

  async function handleSubmit() {
    if (submitting) return
    errorMessage = ''
    submitting = true

    try {
      const data = await login(username, password)
      setUserFromToken(data.access_token, { is_initial_password: data.is_initial_password })
      if (data.is_initial_password) {
        navigateTo('#/password-change')
      } else {
        navigateTo('#/')
      }
    } catch (err) {
      if (err.code === 'ACCOUNT_LOCKED') {
        if (err.unlockAt) {
          startCountdown(err.unlockAt)
        }
        errorMessage = '계정이 잠겼습니다.'
      } else {
        errorMessage = err.message || '로그인에 실패했습니다.'
        lockedUntil = null
        lockCountdown = ''
      }
    } finally {
      submitting = false
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') handleSubmit()
  }
</script>

<div class="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <h1 class="text-2xl font-semibold text-white">회의 및 회의실 관리</h1>
      <p class="text-sm text-neutral-500 mt-1">사내 전용 시스템</p>
    </div>

    <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
      <h2 class="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-6">로그인</h2>

      {#if errorMessage}
        <div class="mb-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
          <p class="text-sm text-red-400">{errorMessage}</p>
          {#if lockedUntil && lockCountdown}
            <p class="text-sm text-red-400 mt-1">잠금 해제까지: {lockCountdown}</p>
          {/if}
        </div>
      {/if}

      <div class="space-y-4">
        <div>
          <label class="text-sm font-medium text-neutral-300 block mb-1.5" for="username">행번</label>
          <input
            id="username"
            type="text"
            bind:value={username}
            onkeydown={handleKeydown}
            placeholder="6자리 행번"
            maxlength="6"
            autocomplete="username"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
          />
        </div>

        <div>
          <label class="text-sm font-medium text-neutral-300 block mb-1.5" for="password">비밀번호</label>
          <input
            id="password"
            type="password"
            bind:value={password}
            onkeydown={handleKeydown}
            placeholder="비밀번호"
            autocomplete="current-password"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
          />
        </div>

        <button
          onclick={handleSubmit}
          disabled={submitting}
          class="w-full rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
        >
          {submitting ? '로그인 중...' : '로그인'}
        </button>
      </div>
    </div>
  </div>
</div>
