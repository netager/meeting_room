<script>
  import { onMount } from 'svelte'
  import { getMyMeetings } from '../lib/api/meetings.js'
  import { navigateTo } from '../router.js'
  import { showToast } from '../lib/stores/toast.js'
  import Badge from '../lib/components/common/Badge.svelte'
  import SkeletonTable from '../lib/components/common/SkeletonTable.svelte'

  let loading = true
  let meetings = []

  function todayStr() {
    return new Date().toISOString().slice(0, 10)
  }

  function weekEndStr() {
    return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  }

  function formatDate(dateStr) {
    const today = todayStr()
    const tomorrowStr = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10)

    if (dateStr === today) return '오늘'
    if (dateStr === tomorrowStr) return '내일'

    const d = new Date(dateStr + 'T00:00:00')
    const days = ['일', '월', '화', '수', '목', '금', '토']
    return `${d.getMonth() + 1}월 ${d.getDate()}일 (${days[d.getDay()]})`
  }

  function groupByDate(items) {
    const groups = {}
    for (const item of items) {
      const key = item.meeting_date
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }

  let grouped = []
  let todayCount = 0
  let weekCount = 0

  onMount(async () => {
    try {
      const today = todayStr()
      const weekEnd = weekEndStr()
      const result = await getMyMeetings({
        date_from: today,
        date_to: weekEnd,
        status: 'SCHEDULED',
        size: 100,
      })
      meetings = result.items || []
      todayCount = meetings.filter((m) => m.meeting_date === today).length
      weekCount = meetings.length
      grouped = groupByDate(meetings)
    } catch (e) {
      showToast(e.message || '회의 목록을 불러오지 못했습니다.', 'error')
    } finally {
      loading = false
    }
  })

  function statusBadgeVariant(status) {
    if (status === 'SCHEDULED') return 'success'
    if (status === 'COMPLETED') return 'neutral'
    return 'error'
  }

  function statusLabel(status) {
    if (status === 'SCHEDULED') return '예정'
    if (status === 'COMPLETED') return '완료'
    if (status === 'CANCELLED') return '취소'
    return status
  }
</script>

<div class="px-6 py-8 max-w-5xl">
  <div class="flex items-center justify-between mb-8">
    <h1 class="text-2xl font-semibold text-white">내 회의</h1>
    <button
      class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors"
      onclick={() => navigateTo('#/meetings/new')}
    >
      + 회의 신청
    </button>
  </div>

  <!-- Stat cards -->
  <div class="grid grid-cols-2 gap-4 mb-8">
    <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
      <p class="text-xs text-neutral-500 uppercase tracking-wider mb-2">오늘 예정</p>
      <p class="text-3xl font-semibold text-white">{todayCount}<span class="text-sm font-normal text-neutral-500 ml-1">건</span></p>
    </div>
    <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
      <p class="text-xs text-neutral-500 uppercase tracking-wider mb-2">이번 주 예정</p>
      <p class="text-3xl font-semibold text-white">{weekCount}<span class="text-sm font-normal text-neutral-500 ml-1">건</span></p>
    </div>
  </div>

  <!-- Upcoming meetings -->
  <div class="rounded-lg bg-[#141414] border border-neutral-800">
    <div class="px-6 py-4 border-b border-neutral-800">
      <h2 class="text-sm font-medium text-neutral-400 uppercase tracking-wider">오늘 & 이번 주 예정 회의</h2>
    </div>

    {#if loading}
      <div class="p-4">
        <SkeletonTable rows={5} cols={5} />
      </div>
    {:else if grouped.length === 0}
      <div class="px-6 py-12 text-center">
        <p class="text-sm text-neutral-500">예정된 회의가 없습니다.</p>
        <button
          class="mt-4 rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
          onclick={() => navigateTo('#/meetings/new')}
        >
          회의 신청하기
        </button>
      </div>
    {:else}
      {#each grouped as [date, items] (date)}
        <div class="border-b border-neutral-800/50 last:border-0">
          <div class="px-6 py-2 bg-[#0f0f0f]">
            <p class="text-xs font-medium text-neutral-400 uppercase tracking-wider">{formatDate(date)}</p>
          </div>
          {#each items as meeting (meeting.id)}
            <div
              class="flex items-center gap-4 px-6 py-3 border-b border-neutral-800/30 last:border-0 cursor-pointer hover:bg-[#1f1f1f] transition-colors"
              role="button"
              tabindex="0"
              onclick={() => navigateTo(`#/meetings/${meeting.id}`)}
              onkeydown={(e) => e.key === 'Enter' && navigateTo(`#/meetings/${meeting.id}`)}
            >
              <div class="shrink-0 text-xs text-neutral-500 w-28">
                {meeting.start_time.slice(0, 5)} ~ {meeting.end_time.slice(0, 5)}
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-white truncate">{meeting.title}</p>
                <p class="text-xs text-neutral-500 mt-0.5">{meeting.room_name}</p>
              </div>
              <div class="shrink-0 text-xs text-neutral-500 mr-2">{meeting.attendee_count}명</div>
              <div class="shrink-0">
                <Badge text={statusLabel(meeting.status)} variant={statusBadgeVariant(meeting.status)} />
              </div>
            </div>
          {/each}
        </div>
      {/each}
    {/if}
  </div>
</div>
