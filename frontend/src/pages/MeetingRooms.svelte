<script>
  import { onMount } from 'svelte'
  import { currentUser } from '../lib/stores/auth.js'
  import { showToast } from '../lib/stores/toast.js'
  import { listRooms, deleteRoom } from '../lib/api/meetingRooms.js'
  import Badge from '../lib/components/common/Badge.svelte'
  import Modal from '../lib/components/common/Modal.svelte'
  import RoomDetailPanel from '../lib/components/rooms/RoomDetailPanel.svelte'
  import RoomFormModal from '../lib/components/rooms/RoomFormModal.svelte'

  let rooms = $state([])
  let loading = $state(true)
  let statusFilter = $state('')

  let detailPanelOpen = $state(false)
  let selectedRoomId = $state(null)

  let formModalOpen = $state(false)
  let formMode = $state('create')
  let formRoom = $state(null)

  let deleteModal = $state({ open: false, room: null, loading: false })

  const STATUS_TABS = [
    { value: '', label: '전체' },
    { value: 'NORMAL', label: '정상' },
    { value: 'TEMP_CLOSED', label: '임시폐쇄' },
    { value: 'CLOSED', label: '폐쇄' },
  ]

  function statusVariant(s) {
    if (s === 'NORMAL') return 'success'
    if (s === 'TEMP_CLOSED') return 'warning'
    if (s === 'CLOSED') return 'error'
    return 'neutral'
  }

  function statusLabel(s) {
    if (s === 'NORMAL') return '정상'
    if (s === 'TEMP_CLOSED') return '임시폐쇄'
    if (s === 'CLOSED') return '폐쇄'
    return s
  }

  async function loadRooms() {
    loading = true
    try {
      rooms = await listRooms(statusFilter ? { status: statusFilter } : {})
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      loading = false
    }
  }

  function openDetail(room) {
    selectedRoomId = room.id
    detailPanelOpen = true
  }

  function openCreate() {
    formMode = 'create'
    formRoom = null
    formModalOpen = true
  }

  function openEdit(e, room) {
    e.stopPropagation()
    formMode = 'edit'
    formRoom = room
    formModalOpen = true
  }

  function openDelete(e, room) {
    e.stopPropagation()
    deleteModal = { open: true, room, loading: false }
  }

  async function handleDelete() {
    if (!deleteModal.room) return
    deleteModal.loading = true
    try {
      await deleteRoom(deleteModal.room.id)
      showToast('회의실이 삭제되었습니다.')
      deleteModal = { open: false, room: null, loading: false }
      await loadRooms()
    } catch (e) {
      showToast(e.message, 'error')
      deleteModal.loading = false
    }
  }

  onMount(loadRooms)

  $effect(() => {
    // reload when statusFilter changes (after mount)
    statusFilter
    if (!loading) loadRooms()
  })

  const canManage = $derived(
    $currentUser?.is_room_manager || $currentUser?.is_admin
  )
</script>

<div class="px-6 py-8 max-w-5xl">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-semibold text-white">회의실 현황</h1>
    {#if canManage}
      <button
        onclick={openCreate}
        class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors"
      >
        + 회의실 추가
      </button>
    {/if}
  </div>

  <!-- Status filter tabs -->
  <div class="flex gap-1 mb-6 border-b border-neutral-800">
    {#each STATUS_TABS as tab (tab.value)}
      <button
        onclick={() => { statusFilter = tab.value }}
        class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {statusFilter === tab.value
          ? 'border-white text-white'
          : 'border-transparent text-neutral-400 hover:text-neutral-200'}"
      >
        {tab.label}
      </button>
    {/each}
  </div>

  <!-- Content -->
  {#if loading}
    <div class="grid grid-cols-3 gap-4">
      {#each Array.from({ length: 6 }, (__, i) => i) as i (i)}
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-5 space-y-3">
          <div class="h-4 w-3/4 rounded bg-neutral-800 animate-pulse"></div>
          <div class="h-3 w-1/2 rounded bg-neutral-800 animate-pulse"></div>
          <div class="h-3 w-1/3 rounded bg-neutral-800 animate-pulse"></div>
        </div>
      {/each}
    </div>
  {:else if rooms.length === 0}
    <div class="rounded-lg bg-[#141414] border border-neutral-800 px-4 py-12 text-center">
      <p class="text-neutral-500">등록된 회의실이 없습니다.</p>
      {#if canManage}
        <button
          onclick={openCreate}
          class="mt-4 rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
        >
          회의실 등록
        </button>
      {/if}
    </div>
  {:else}
    <div class="grid grid-cols-3 gap-4">
      {#each rooms as room (room.id)}
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div
          onclick={() => openDetail(room)}
          class="relative rounded-lg bg-[#141414] border border-neutral-800 p-5 cursor-pointer hover:bg-[#1f1f1f] transition-colors"
        >
          <!-- Manage actions (top-right) -->
          {#if canManage}
            <div class="absolute top-3 right-3 flex gap-2" role="group">
              <button
                onclick={(e) => openEdit(e, room)}
                class="text-neutral-500 hover:text-white transition-colors p-1"
                title="수정"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                </svg>
              </button>
              {#if $currentUser?.is_admin}
                <button
                  onclick={(e) => openDelete(e, room)}
                  class="text-neutral-500 hover:text-red-400 transition-colors p-1"
                  title="삭제"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              {/if}
            </div>
          {/if}

          <!-- Room info -->
          <div class="pr-12">
            <p class="text-sm font-medium text-white truncate">{room.name}</p>
            <p class="text-xs text-neutral-500 mt-1 truncate">{room.location}</p>
            <p class="text-xs text-neutral-600 mt-0.5">{room.dept_code}</p>
          </div>

          <!-- Footer: status + equipment count -->
          <div class="flex items-center justify-between mt-4">
            <Badge text={statusLabel(room.status)} variant={statusVariant(room.status)} />
            <span class="text-xs text-neutral-500">
              집기 {room.equipment?.length ?? 0}개
            </span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Room detail slide panel -->
<RoomDetailPanel
  roomId={selectedRoomId}
  open={detailPanelOpen}
  onClose={() => { detailPanelOpen = false }}
/>

<!-- Create / Edit form modal -->
<RoomFormModal
  mode={formMode}
  room={formRoom}
  open={formModalOpen}
  onClose={() => { formModalOpen = false }}
  onSave={loadRooms}
/>

<!-- Delete confirmation modal -->
<Modal
  title="회의실을 삭제하시겠습니까?"
  open={deleteModal.open}
  onClose={() => { deleteModal = { open: false, room: null, loading: false } }}
>
  <p class="text-sm text-neutral-300">
    <span class="text-white font-medium">{deleteModal.room?.name}</span>을(를) 삭제합니다.<br />
    <span class="text-neutral-500">연결된 회의나 집기가 있으면 삭제할 수 없습니다.</span>
  </p>
  {#snippet footer()}
    <button
      onclick={() => { deleteModal = { open: false, room: null, loading: false } }}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      취소
    </button>
    <button
      onclick={handleDelete}
      disabled={deleteModal.loading}
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors disabled:opacity-50"
    >
      {deleteModal.loading ? '삭제 중...' : '삭제'}
    </button>
  {/snippet}
</Modal>
