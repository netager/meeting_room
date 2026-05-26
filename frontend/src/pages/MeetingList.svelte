<script>
  import { onMount } from 'svelte'
  import { listMeetings } from '../lib/api/meetings.js'
  import { navigateTo } from '../router.js'
  import { showToast } from '../lib/stores/toast.js'
  import Badge from '../lib/components/common/Badge.svelte'
  import Table from '../lib/components/common/Table.svelte'
  import Pagination from '../lib/components/common/Pagination.svelte'
  import SkeletonTable from '../lib/components/common/SkeletonTable.svelte'

  let loading = true
  let data = { items: [], total: 0, page: 1, pages: 0, size: 20 }

  // Filter state
  let statusFilter = ''
  let dateFrom = ''
  let dateTo = ''
  let myOnly = false
  let page = 1

  const HEADERS = [
    { key: 'meeting_date', label: '날짜' },
    { key: 'time', label: '시간' },
    { key: 'title', label: '회의명' },
    { key: 'room_name', label: '회의실' },
    { key: 'attendee_count', label: '참석자' },
    { key: 'status', label: '상태' },
  ]

  function statusLabel(status) {
    if (status === 'SCHEDULED') return '예정'
    if (status === 'COMPLETED') return '완료'
    if (status === 'CANCELLED') return '취소'
    return status
  }

  function statusBadgeVariant(status) {
    if (status === 'SCHEDULED') return 'success'
    if (status === 'COMPLETED') return 'neutral'
    return 'error'
  }

  async function fetchMeetings() {
    loading = true
    try {
      const params = { page, size: 20 }
      if (statusFilter) params.status = statusFilter
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      if (myOnly) params.my = true
      data = await listMeetings(params)
    } catch (e) {
      showToast(e.message || '회의 목록을 불러오지 못했습니다.', 'error')
    } finally {
      loading = false
    }
  }

  function onFilterChange() {
    page = 1
    fetchMeetings()
  }

  function onPageChange(p) {
    page = p
    fetchMeetings()
  }

  onMount(fetchMeetings)

  const STATUS_TABS = [
    { value: '', label: '전체' },
    { value: 'SCHEDULED', label: '예정' },
    { value: 'COMPLETED', label: '완료' },
    { value: 'CANCELLED', label: '취소' },
  ]
</script>

<div class="px-6 py-8 max-w-5xl">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-semibold text-white">전체 회의</h1>
    <button
      class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors"
      onclick={() => navigateTo('#/meetings/new')}
    >
      + 회의 신청
    </button>
  </div>

  <!-- Filters -->
  <div class="rounded-lg bg-[#141414] border border-neutral-800 p-4 mb-4 space-y-3">
    <!-- Status tabs -->
    <div class="flex gap-2 flex-wrap">
      {#each STATUS_TABS as tab (tab.value)}
        <button
          class="px-3 py-1.5 rounded-lg text-sm transition-colors {statusFilter === tab.value
            ? 'bg-white text-black font-medium'
            : 'text-neutral-400 border border-neutral-700 hover:bg-[#1f1f1f] hover:text-white'}"
          onclick={() => { statusFilter = tab.value; onFilterChange() }}
        >
          {tab.label}
        </button>
      {/each}
    </div>

    <!-- Date range + my meetings toggle -->
    <div class="flex items-center gap-4 flex-wrap">
      <div class="flex items-center gap-2">
        <span class="text-xs text-neutral-500">기간</span>
        <input
          type="date"
          bind:value={dateFrom}
          onchange={onFilterChange}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-white px-3 py-1.5 text-sm focus:outline-none focus:border-neutral-600"
        />
        <span class="text-neutral-500 text-sm">~</span>
        <input
          type="date"
          bind:value={dateTo}
          onchange={onFilterChange}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-white px-3 py-1.5 text-sm focus:outline-none focus:border-neutral-600"
        />
      </div>
      <label class="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          bind:checked={myOnly}
          onchange={onFilterChange}
          class="w-4 h-4 rounded accent-white"
        />
        <span class="text-sm text-neutral-300">내 회의만</span>
      </label>
    </div>
  </div>

  <!-- Table -->
  <div class="rounded-lg bg-[#141414] border border-neutral-800">
    {#if loading}
      <div class="p-4">
        <SkeletonTable rows={5} cols={6} />
      </div>
    {:else}
      <Table
        headers={HEADERS}
        rows={data.items}
        onRowClick={(row) => navigateTo(`#/meetings/${row.id}`)}
      >
        {#snippet cell(row, col)}
          {#if col.key === 'time'}
            <span class="text-neutral-400">{row.start_time.slice(0, 5)} ~ {row.end_time.slice(0, 5)}</span>
          {:else if col.key === 'status'}
            <Badge text={statusLabel(row.status)} variant={statusBadgeVariant(row.status)} />
          {:else if col.key === 'attendee_count'}
            <span>{row.attendee_count}명</span>
          {:else}
            {row[col.key] ?? '—'}
          {/if}
        {/snippet}
        {#snippet empty()}
          <tr>
            <td colspan={HEADERS.length} class="px-4 py-12 text-center text-sm text-neutral-500">
              조회 조건에 맞는 회의가 없습니다.
            </td>
          </tr>
        {/snippet}
      </Table>
      <div class="px-4">
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          onPageChange={onPageChange}
        />
      </div>
    {/if}
  </div>
</div>
