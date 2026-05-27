<script>
  import { onMount } from 'svelte'
  import Pagination from '../lib/components/common/Pagination.svelte'
  import SkeletonTable from '../lib/components/common/SkeletonTable.svelte'
  import { getNotifications } from '../lib/api/notifications.js'

  let loading = $state(true)
  let items = $state([])
  let total = $state(0)
  let page = $state(1)
  let pages = $state(0)
  const size = 20

  const EVENT_TYPE_LABELS = {
    CREATED: '회의 신청',
    UPDATED: '회의 수정',
    CANCELLED: '회의 취소',
    COMPLETED: '회의 완료',
    ATTENDEE_ADDED: '참석자 추가',
    ATTENDEE_REMOVED: '참석자 제거',
    DIRECT: '직접 메시지',
  }

  const STATUS_LABELS = {
    PENDING: '대기',
    SENDING: '발송 중',
    SENT: '수신',
    FAILED: '실패',
  }

  const EVENT_TYPE_BADGE = {
    CREATED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    UPDATED: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    CANCELLED: 'bg-neutral-800 text-neutral-400 border-neutral-700',
    COMPLETED: 'bg-green-500/10 text-green-400 border-green-500/20',
    ATTENDEE_ADDED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    ATTENDEE_REMOVED: 'bg-neutral-800 text-neutral-400 border-neutral-700',
    DIRECT: 'bg-neutral-800 text-neutral-400 border-neutral-700',
  }

  const STATUS_BADGE = {
    PENDING: 'bg-neutral-800 text-neutral-400 border-neutral-700',
    SENDING: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    SENT: 'bg-green-500/10 text-green-400 border-green-500/20',
    FAILED: 'bg-red-500/10 text-red-400 border-red-500/20',
  }

  function getEventTypeBadge(eventType) {
    return EVENT_TYPE_BADGE[eventType] || 'bg-neutral-800 text-neutral-400 border-neutral-700'
  }

  function getStatusBadge(status) {
    return STATUS_BADGE[status] || 'bg-neutral-800 text-neutral-400 border-neutral-700'
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  async function loadPage(p = 1) {
    loading = true
    try {
      const data = await getNotifications({ page: p, size })
      items = data.items || []
      total = data.total || 0
      pages = data.pages || 0
      page = data.page || p
    } catch {
      items = []
      total = 0
      pages = 0
    } finally {
      loading = false
    }
  }

  function handlePageChange(p) {
    loadPage(p)
  }

  onMount(() => {
    loadPage(1)
  })
</script>

<div class="px-6 py-8 max-w-5xl">
  <!-- Page header -->
  <div class="mb-6">
    <h1 class="text-2xl font-semibold text-white">알림</h1>
    <p class="mt-1 text-sm text-neutral-400">내 회의 관련 알림 목록입니다.</p>
  </div>

  <!-- Table -->
  <div class="rounded-lg bg-[#141414] border border-neutral-800">
    {#if loading}
      <SkeletonTable rows={5} cols={4} />
    {:else if items.length === 0}
      <div class="px-6 py-16 text-sm text-neutral-500 text-center">알림이 없습니다.</div>
    {:else}
      <!-- Header row -->
      <div
        class="grid grid-cols-[120px_1fr_80px_160px] gap-4 px-6 py-3 border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider"
      >
        <span>이벤트 유형</span>
        <span>메시지</span>
        <span>상태</span>
        <span>수신 시각</span>
      </div>

      <!-- Data rows -->
      {#each items as notification (notification.id)}
        <div
          class="grid grid-cols-[120px_1fr_80px_160px] gap-4 px-6 py-4 border-b border-neutral-800/50 hover:bg-[#1f1f1f] transition-colors items-start"
        >
          <!-- Event type badge -->
          <div>
            <span
              class="inline-block text-xs px-2 py-1 rounded border {getEventTypeBadge(notification.event_type)}"
            >
              {EVENT_TYPE_LABELS[notification.event_type] || notification.event_type}
            </span>
          </div>

          <!-- Message -->
          <p class="text-sm text-neutral-300 leading-relaxed">
            {notification.message}
          </p>

          <!-- Status badge -->
          <div>
            <span
              class="inline-block text-xs px-2 py-1 rounded border {getStatusBadge(notification.status)}"
            >
              {STATUS_LABELS[notification.status] || notification.status}
            </span>
          </div>

          <!-- Received at -->
          <span class="text-xs text-neutral-500">
            {formatDateTime(notification.created_at)}
          </span>
        </div>
      {/each}

      <!-- Pagination -->
      <div class="px-6 pb-4">
        <Pagination {page} {pages} {total} onPageChange={handlePageChange} />
      </div>
    {/if}
  </div>
</div>
