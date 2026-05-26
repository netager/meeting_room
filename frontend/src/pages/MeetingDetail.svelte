<script>
  import { onMount, onDestroy } from 'svelte'
  import { get as storeGet } from 'svelte/store'
  import { currentUser } from '../lib/stores/auth.js'
  import { navigateTo } from '../router.js'
  import { showToast } from '../lib/stores/toast.js'
  import {
    getMeeting,
    getFiles,
    cancelMeeting,
    completeMeeting,
    downloadFile,
    deleteFile,
    addAttendee,
    removeAttendee,
  } from '../lib/api/meetings.js'
  import { searchEmployees } from '../lib/api/employees.js'
  import Modal from '../lib/components/common/Modal.svelte'
  import Badge from '../lib/components/common/Badge.svelte'
  import SlidePanel from '../lib/components/common/SlidePanel.svelte'

  let { meetingId } = $props()

  // ── Data ──────────────────────────────────────────────────────────
  let meeting = $state(null)
  let files = $state([])
  let loading = $state(true)
  let loadError = $state('')

  // ── Modals ────────────────────────────────────────────────────────
  let showCancelModal = $state(false)
  let showCompleteModal = $state(false)
  let showDeleteFileModal = $state(false)
  let fileToDelete = $state(null)

  // ── Action state ──────────────────────────────────────────────────
  let cancelling = $state(false)
  let completing = $state(false)
  let downloadingFileId = $state(null)

  // ── Attendee panel ────────────────────────────────────────────────
  let showAttendeePanel = $state(false)
  let attendeeQuery = $state('')
  let attendeeResults = $state([])
  let attendeeLoading = $state(false)
  let addingAttendee = $state(false)
  let searchTimer = null

  // ── Permissions ───────────────────────────────────────────────────
  const user = storeGet(currentUser)
  let isAdmin = $derived(user?.is_admin ?? false)
  let isOrganizer = $derived(meeting?.created_by === user?.emp_no)
  let isScheduled = $derived(meeting?.status === 'SCHEDULED')
  let canModify = $derived((isOrganizer || isAdmin) && isScheduled)
  let canComplete = $derived(isAdmin && isScheduled)

  // ── Load ───────────────────────────────────────────────────────────
  onMount(async () => {
    await loadData()
  })

  onDestroy(() => {
    clearTimeout(searchTimer)
  })

  async function loadData() {
    loading = true
    loadError = ''
    try {
      const [m, f] = await Promise.all([getMeeting(meetingId), getFiles(meetingId)])
      meeting = m
      files = Array.isArray(f) ? f : (f?.items ?? [])
    } catch (e) {
      loadError = e.message || '회의 정보를 불러올 수 없습니다.'
    } finally {
      loading = false
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────
  function formatDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr + 'T00:00:00')
    const days = ['일', '월', '화', '수', '목', '금', '토']
    return `${dateStr} (${days[d.getDay()]})`
  }

  function formatTime(t) {
    return (t || '').slice(0, 5)
  }

  function formatSize(bytes) {
    if (!bytes) return ''
    if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`
    return `${(bytes / 1024).toFixed(0)}KB`
  }

  function statusVariant(status) {
    if (status === 'SCHEDULED') return 'success'
    if (status === 'COMPLETED') return 'neutral'
    if (status === 'CANCELLED') return 'error'
    return 'neutral'
  }

  function statusLabel(status) {
    if (status === 'SCHEDULED') return '예정'
    if (status === 'COMPLETED') return '완료'
    if (status === 'CANCELLED') return '취소'
    return status ?? ''
  }

  function fileIcon(mime) {
    if (!mime) return '📄'
    if (mime.includes('pdf')) return '📕'
    if (mime.includes('spreadsheet') || mime.includes('excel')) return '📊'
    if (mime.includes('presentation') || mime.includes('powerpoint')) return '📑'
    if (mime.includes('image')) return '🖼'
    if (mime.includes('zip')) return '📦'
    return '📄'
  }

  function canDeleteFile(file) {
    return isAdmin || file.uploaded_by === user?.emp_no
  }

  // ── Cancel meeting ────────────────────────────────────────────────
  async function handleCancelConfirm() {
    cancelling = true
    try {
      await cancelMeeting(meetingId)
      showCancelModal = false
      showToast('회의가 취소되었습니다.')
      await loadData()
    } catch (e) {
      showToast(e.message || '취소에 실패했습니다.', 'error')
    } finally {
      cancelling = false
    }
  }

  // ── Complete meeting ──────────────────────────────────────────────
  async function handleCompleteConfirm() {
    completing = true
    try {
      await completeMeeting(meetingId)
      showCompleteModal = false
      showToast('회의가 완료 처리되었습니다.')
      await loadData()
    } catch (e) {
      showToast(e.message || '완료 처리에 실패했습니다.', 'error')
    } finally {
      completing = false
    }
  }

  // ── File download ─────────────────────────────────────────────────
  async function handleDownload(fileId) {
    downloadingFileId = fileId
    try {
      await downloadFile(meetingId, fileId)
    } catch (e) {
      showToast(e.message || '다운로드에 실패했습니다.', 'error')
    } finally {
      downloadingFileId = null
    }
  }

  // ── File delete ───────────────────────────────────────────────────
  function requestDeleteFile(file) {
    fileToDelete = file
    showDeleteFileModal = true
  }

  async function handleDeleteFileConfirm() {
    if (!fileToDelete) return
    const target = fileToDelete
    showDeleteFileModal = false
    fileToDelete = null
    try {
      await deleteFile(meetingId, target.id)
      files = files.filter((f) => f.id !== target.id)
      showToast('파일이 삭제되었습니다.')
    } catch (e) {
      showToast(e.message || '파일 삭제에 실패했습니다.', 'error')
    }
  }

  // ── Attendee management ───────────────────────────────────────────
  function openAttendeePanel() {
    attendeeQuery = ''
    attendeeResults = []
    showAttendeePanel = true
  }

  function onAttendeeInput(e) {
    attendeeQuery = e.target.value
    clearTimeout(searchTimer)
    if (!attendeeQuery.trim()) {
      attendeeResults = []
      return
    }
    searchTimer = setTimeout(async () => {
      attendeeLoading = true
      try {
        attendeeResults = await searchEmployees(attendeeQuery)
      } catch {
        attendeeResults = []
      } finally {
        attendeeLoading = false
      }
    }, 300)
  }

  async function handleAddAttendee(emp) {
    addingAttendee = true
    try {
      await addAttendee(meetingId, emp.emp_no)
      await loadData()
      showToast('참석자가 추가되었습니다.')
      attendeeQuery = ''
      attendeeResults = []
    } catch (e) {
      showToast(e.message || '참석자 추가에 실패했습니다.', 'error')
    } finally {
      addingAttendee = false
    }
  }

  async function handleRemoveAttendee(empNo) {
    try {
      await removeAttendee(meetingId, empNo)
      if (meeting) {
        meeting = { ...meeting, attendees: meeting.attendees.filter((a) => a.emp_no !== empNo) }
      }
      showToast('참석자가 제거되었습니다.')
    } catch (e) {
      showToast(e.message || '참석자 제거에 실패했습니다.', 'error')
    }
  }
</script>

<!-- Cancel confirm modal -->
<Modal title="회의를 취소하시겠습니까?" open={showCancelModal} onClose={() => (showCancelModal = false)}>
  <p class="text-sm text-neutral-300">
    취소된 회의는 되돌릴 수 없으며, 참석자에게 취소 알림이 발송됩니다.
  </p>
  {#snippet footer()}
    <button
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
      onclick={() => (showCancelModal = false)}
      autofocus
    >
      닫기
    </button>
    <button
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors disabled:opacity-50"
      onclick={handleCancelConfirm}
      disabled={cancelling}
    >
      {cancelling ? '처리 중...' : '취소 처리'}
    </button>
  {/snippet}
</Modal>

<!-- Complete confirm modal -->
<Modal
  title="회의를 완료 처리하시겠습니까?"
  open={showCompleteModal}
  onClose={() => (showCompleteModal = false)}
>
  <p class="text-sm text-neutral-300">회의를 완료로 처리합니다.</p>
  {#snippet footer()}
    <button
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
      onclick={() => (showCompleteModal = false)}
      autofocus
    >
      취소
    </button>
    <button
      class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
      onclick={handleCompleteConfirm}
      disabled={completing}
    >
      {completing ? '처리 중...' : '완료 처리'}
    </button>
  {/snippet}
</Modal>

<!-- Delete file confirm modal -->
<Modal
  title="파일을 삭제하시겠습니까?"
  open={showDeleteFileModal}
  onClose={() => {
    showDeleteFileModal = false
    fileToDelete = null
  }}
>
  <p class="text-sm text-neutral-300">
    {fileToDelete?.original_name ?? '파일'}을 삭제합니다. 복구할 수 없습니다.
  </p>
  {#snippet footer()}
    <button
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
      onclick={() => {
        showDeleteFileModal = false
        fileToDelete = null
      }}
      autofocus
    >
      취소
    </button>
    <button
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors"
      onclick={handleDeleteFileConfirm}
    >
      삭제
    </button>
  {/snippet}
</Modal>

<!-- Attendee add slide panel -->
<SlidePanel title="참석자 추가" open={showAttendeePanel} onClose={() => (showAttendeePanel = false)}>
  <div class="space-y-4">
    <input
      type="text"
      value={attendeeQuery}
      oninput={onAttendeeInput}
      placeholder="이름 또는 행번으로 검색..."
      class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
    />

    {#if attendeeLoading}
      <p class="text-sm text-neutral-500 px-1">검색 중...</p>
    {:else if attendeeQuery.trim() && attendeeResults.length === 0}
      <p class="text-sm text-neutral-500 px-1">검색 결과 없음</p>
    {:else if attendeeResults.length > 0}
      {@const existingEmpNos = new Set((meeting?.attendees ?? []).map((a) => a.emp_no))}
      <ul class="space-y-1">
        {#each attendeeResults.slice(0, 10) as emp (emp.emp_no)}
          {@const alreadyAdded = existingEmpNos.has(emp.emp_no)}
          <li>
            <button
              type="button"
              class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors {alreadyAdded
                ? 'opacity-40 cursor-not-allowed'
                : 'hover:bg-[#1f1f1f] text-neutral-200 cursor-pointer'}"
              disabled={alreadyAdded || addingAttendee}
              onclick={() => handleAddAttendee(emp)}
            >
              <span class="font-medium">{emp.name}</span>
              {#if emp.dept_name}<span class="text-neutral-500 text-xs">{emp.dept_name}</span>{/if}
              {#if emp.job_title}<span class="text-neutral-500 text-xs">· {emp.job_title}</span>{/if}
              {#if alreadyAdded}
                <span class="ml-auto text-xs text-neutral-600">이미 추가됨</span>
              {/if}
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm text-neutral-600 px-1">이름 또는 행번을 입력하세요</p>
    {/if}
  </div>
</SlidePanel>

<!-- Main content -->
{#if loading}
  <div class="px-6 py-8 max-w-5xl space-y-6">
    <div class="h-8 w-64 rounded bg-neutral-800 animate-pulse"></div>
    <div class="grid grid-cols-2 gap-6">
      {#each Array.from({ length: 6 }, (_, i) => i) as i (i)}
        <div class="h-5 rounded bg-neutral-800 animate-pulse"></div>
      {/each}
    </div>
    <div class="h-24 rounded-lg bg-neutral-800 animate-pulse"></div>
  </div>
{:else if loadError || !meeting}
  <div class="px-6 py-8 max-w-5xl">
    <p class="text-sm text-neutral-400">
      {loadError || '존재하지 않는 회의이거나 접근 권한이 없습니다.'}
    </p>
    <button
      class="mt-4 text-sm text-neutral-400 hover:text-white transition-colors"
      onclick={() => navigateTo('#/meetings')}
    >
      ← 목록으로
    </button>
  </div>
{:else}
  <div class="px-6 py-8 max-w-5xl">
    <!-- Header row -->
    <div class="flex items-start justify-between mb-6 gap-4">
      <div class="flex items-center gap-3 min-w-0">
        <button
          class="text-sm text-neutral-400 hover:text-white transition-colors shrink-0"
          onclick={() => navigateTo('#/meetings')}
        >
          ← 목록으로
        </button>
        <span class="text-neutral-700">|</span>
        <h1 class="text-2xl font-semibold text-white truncate">{meeting.title}</h1>
        <Badge text={statusLabel(meeting.status)} variant={statusVariant(meeting.status)} />
      </div>

      <!-- Action buttons -->
      {#if canModify || canComplete}
        <div class="flex items-center gap-2 shrink-0">
          {#if canModify}
            <button
              class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
              onclick={() => navigateTo(`#/meetings/${meetingId}/edit`)}
            >
              수정
            </button>
            <button
              class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors"
              onclick={() => (showCancelModal = true)}
            >
              취소
            </button>
          {/if}
          {#if canComplete}
            <button
              class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors"
              onclick={() => (showCompleteModal = true)}
            >
              완료 처리
            </button>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Body: two column grid -->
    <div class="grid grid-cols-2 gap-6">
      <!-- Left column -->
      <div class="space-y-6">
        <!-- Meeting info card -->
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6 space-y-4">
          <h2 class="text-xs font-medium text-neutral-400 uppercase tracking-wider">회의 정보</h2>

          <div class="space-y-3 text-sm">
            <div class="flex gap-3">
              <span class="text-neutral-500 w-16 shrink-0">회의실</span>
              <span class="text-neutral-200">{meeting.room_name || '-'}</span>
            </div>
            <div class="flex gap-3">
              <span class="text-neutral-500 w-16 shrink-0">날짜</span>
              <span class="text-neutral-200">{formatDate(String(meeting.meeting_date))}</span>
            </div>
            <div class="flex gap-3">
              <span class="text-neutral-500 w-16 shrink-0">시간</span>
              <span class="text-neutral-200">
                {formatTime(String(meeting.start_time))} ~ {formatTime(String(meeting.end_time))}
              </span>
            </div>
            <div class="flex gap-3">
              <span class="text-neutral-500 w-16 shrink-0">주최자</span>
              <span class="text-neutral-200">{meeting.created_by_name || meeting.created_by}</span>
            </div>
          </div>

          {#if meeting.agenda}
            <div class="pt-2 border-t border-neutral-800">
              <p class="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">안건</p>
              <p class="text-sm text-neutral-300 leading-relaxed whitespace-pre-wrap">{meeting.agenda}</p>
            </div>
          {/if}
        </div>
      </div>

      <!-- Right column -->
      <div class="space-y-6">
        <!-- Attendees card -->
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-xs font-medium text-neutral-400 uppercase tracking-wider">
              참석자 ({meeting.attendees?.length ?? 0}명)
            </h2>
            {#if canModify}
              <button
                class="text-xs text-neutral-400 hover:text-white transition-colors border border-neutral-700 rounded px-2 py-1"
                onclick={openAttendeePanel}
              >
                + 참석자 추가
              </button>
            {/if}
          </div>

          {#if meeting.attendees && meeting.attendees.length > 0}
            <ul class="space-y-2">
              {#each meeting.attendees as a (a.emp_no)}
                {@const isCreator = a.emp_no === meeting.created_by}
                <li class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="text-sm text-neutral-200 font-medium">{a.name}</span>
                    {#if a.dept_code}
                      <span class="text-xs text-neutral-500">{a.dept_code}</span>
                    {/if}
                    {#if a.rank}
                      <span class="text-xs text-neutral-500">· {a.rank}</span>
                    {/if}
                    {#if isCreator}
                      <span class="text-xs text-neutral-600">(주최자)</span>
                    {/if}
                  </div>
                  {#if canModify && !isCreator}
                    <button
                      type="button"
                      class="text-neutral-600 hover:text-red-400 transition-colors text-xs shrink-0"
                      onclick={() => handleRemoveAttendee(a.emp_no)}
                      title="{a.name} 제거"
                    >
                      ✕
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm text-neutral-600">참석자 없음</p>
          {/if}
        </div>

        <!-- Files card -->
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
          <h2 class="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
            첨부파일 ({files.length}개)
          </h2>

          {#if files.length > 0}
            <ul class="space-y-2">
              {#each files as file (file.id)}
                <li class="flex items-center gap-2 rounded-lg bg-neutral-900 border border-neutral-800 px-3 py-2.5">
                  <span class="text-base shrink-0">{fileIcon(file.mime_type)}</span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm text-neutral-200 truncate">{file.original_name}</p>
                    <p class="text-xs text-neutral-500">{formatSize(file.size)}</p>
                  </div>
                  <button
                    class="text-xs text-neutral-400 hover:text-white border border-neutral-700 rounded px-2 py-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                    onclick={() => handleDownload(file.id)}
                    disabled={downloadingFileId === file.id}
                  >
                    {downloadingFileId === file.id ? '다운로드 중...' : '다운로드'}
                  </button>
                  {#if canDeleteFile(file)}
                    <button
                      class="text-neutral-600 hover:text-red-400 transition-colors text-xs shrink-0"
                      onclick={() => requestDeleteFile(file)}
                      title="파일 삭제"
                    >
                      ✕
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm text-neutral-600">첨부된 파일이 없습니다.</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
