<script>
  import { changePassword } from '../lib/api/auth.js'
  import { currentUser, setUserFromToken } from '../lib/stores/auth.js'
  import { showToast } from '../lib/stores/toast.js'
  import { getAccessToken } from '../lib/api/client.js'
  import { navigateTo } from '../router.js'

  let currentPw = $state('')
  let newPw = $state('')
  let confirmPw = $state('')
  let submitting = $state(false)
  let errorMessage = $state('')

  // Real-time policy checks
  let policyMinLength = $derived(newPw.length >= 8)
  let policyHasLetter = $derived(/[a-zA-Z]/.test(newPw))
  let policyHasDigit = $derived(/[0-9]/.test(newPw))
  let confirmMatch = $derived(confirmPw.length > 0 && newPw === confirmPw)
  let confirmMismatch = $derived(confirmPw.length > 0 && newPw !== confirmPw)

  async function handleSubmit() {
    if (submitting) return
    errorMessage = ''

    if (!policyMinLength || !policyHasLetter || !policyHasDigit) {
      errorMessage = '비밀번호 정책을 확인해 주세요.'
      return
    }
    if (newPw !== confirmPw) {
      errorMessage = '새 비밀번호가 일치하지 않습니다.'
      return
    }

    submitting = true
    try {
      await changePassword(currentPw, newPw)
      // Update currentUser's is_initial_password flag
      const token = getAccessToken()
      if (token) {
        setUserFromToken(token, { is_initial_password: false })
      } else {
        currentUser.update((u) => u ? { ...u, is_initial_password: false } : null)
      }
      showToast('비밀번호가 변경되었습니다.')
      navigateTo('#/')
    } catch (err) {
      errorMessage = err.message || '비밀번호 변경에 실패했습니다.'
    } finally {
      submitting = false
    }
  }
</script>

<div class="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
  <div class="w-full max-w-sm">
    <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
      <h2 class="text-lg font-semibold text-white mb-1">비밀번호 변경 필요</h2>
      <p class="text-sm text-neutral-400 mb-6">처음 로그인하셨습니다. 보안을 위해 비밀번호를 변경해 주세요.</p>

      {#if errorMessage}
        <div class="mb-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
          <p class="text-sm text-red-400">{errorMessage}</p>
        </div>
      {/if}

      <div class="space-y-4">
        <div>
          <label class="text-sm font-medium text-neutral-300 block mb-1.5" for="current-pw">현재 비밀번호 (행번)</label>
          <input
            id="current-pw"
            type="password"
            bind:value={currentPw}
            autocomplete="current-password"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
          />
        </div>

        <div>
          <label class="text-sm font-medium text-neutral-300 block mb-1.5" for="new-pw">새 비밀번호</label>
          <input
            id="new-pw"
            type="password"
            bind:value={newPw}
            autocomplete="new-password"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
          />
          <div class="mt-2 space-y-1">
            <p class="text-xs {policyMinLength ? 'text-green-400' : 'text-neutral-500'}">
              {policyMinLength ? '✓' : '✗'} 8자 이상
            </p>
            <p class="text-xs {policyHasLetter ? 'text-green-400' : 'text-neutral-500'}">
              {policyHasLetter ? '✓' : '✗'} 영문 포함
            </p>
            <p class="text-xs {policyHasDigit ? 'text-green-400' : 'text-neutral-500'}">
              {policyHasDigit ? '✓' : '✗'} 숫자 포함
            </p>
          </div>
        </div>

        <div>
          <label class="text-sm font-medium text-neutral-300 block mb-1.5" for="confirm-pw">새 비밀번호 확인</label>
          <input
            id="confirm-pw"
            type="password"
            bind:value={confirmPw}
            autocomplete="new-password"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600 {confirmMismatch ? 'border-red-500/50' : ''}"
          />
          {#if confirmMismatch}
            <p class="text-xs text-red-400 mt-1">비밀번호가 일치하지 않습니다.</p>
          {:else if confirmMatch}
            <p class="text-xs text-green-400 mt-1">✓ 비밀번호가 일치합니다.</p>
          {/if}
        </div>

        <button
          onclick={handleSubmit}
          disabled={submitting}
          class="w-full rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
        >
          {submitting ? '처리 중...' : '변경 완료'}
        </button>
      </div>
    </div>
  </div>
</div>
