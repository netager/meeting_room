<script>
  import SlidePanel from '../common/SlidePanel.svelte'
  import Badge from '../common/Badge.svelte'
  import RoomAvailabilityPanel from './RoomAvailabilityPanel.svelte'
  import { getRoom } from '../../api/meetingRooms.js'
  import { showToast } from '../../stores/toast.js'

  let { roomId, open = false, onClose, selectedDate = null } = $props()

  let room = $state(null)
  let loading = $state(false)
  let activeTab = $state('info')

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

  $effect(() => {
    if (open && roomId) {
      loading = true
      room = null
      getRoom(roomId)
        .then((r) => { room = r })
        .catch((e) => showToast(e.message, 'error'))
        .finally(() => { loading = false })
    }
  })
</script>

<SlidePanel open={open} title={room?.name ?? '회의실 상세'} onClose={onClose}>
  {#if loading}
    <div class="space-y-3">
      {#each Array.from({ length: 4 }, (__, i) => i) as i (i)}
        <div class="h-5 rounded bg-neutral-800 animate-pulse"></div>
      {/each}
    </div>
  {:else if room}
    <!-- Tab bar -->
    <div class="flex gap-1 mb-6 border-b border-neutral-800">
      {#each [['info', '기본 정보'], ['schedule', '예약 현황']] as [tab, label] (tab)}
        <button
          onclick={() => { activeTab = tab }}
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === tab
            ? 'border-white text-white'
            : 'border-transparent text-neutral-400 hover:text-neutral-200'}"
        >
          {label}
        </button>
      {/each}
    </div>

    {#if activeTab === 'info'}
      <div class="space-y-5">
        <!-- Header info -->
        <div class="space-y-3">
          <div>
            <p class="text-xs text-neutral-500 mb-1">상태</p>
            <Badge text={statusLabel(room.status)} variant={statusVariant(room.status)} />
          </div>
          <div>
            <p class="text-xs text-neutral-500 mb-1">이름</p>
            <p class="text-sm text-white">{room.name}</p>
          </div>
          <div>
            <p class="text-xs text-neutral-500 mb-1">위치</p>
            <p class="text-sm text-neutral-300">{room.location}</p>
          </div>
          <div>
            <p class="text-xs text-neutral-500 mb-1">담당 부서</p>
            <p class="text-sm text-neutral-300">{room.dept_code}</p>
          </div>
        </div>

        <!-- Equipment -->
        <div>
          <p class="text-xs text-neutral-500 uppercase tracking-wider mb-3">집기 목록 ({room.equipment?.length ?? 0}개)</p>
          {#if room.equipment == null || room.equipment.length === 0}
            <p class="text-sm text-neutral-500">등록된 집기가 없습니다.</p>
          {:else}
            <div class="rounded-lg border border-neutral-800 overflow-hidden">
              <table class="w-full text-sm">
                <thead>
                  <tr>
                    {#each ['집기명', '수량', '비고'] as h (h)}
                      <th class="px-3 py-2 text-left border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider">{h}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each room.equipment as eq (eq.id)}
                    <tr class="border-b border-neutral-800/50">
                      <td class="px-3 py-2 text-neutral-300">{eq.name}</td>
                      <td class="px-3 py-2 text-neutral-400">{eq.quantity}</td>
                      <td class="px-3 py-2 text-neutral-500">{eq.note ?? '—'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      </div>
    {:else}
      <RoomAvailabilityPanel roomId={room.id} initialDate={selectedDate} />
    {/if}
  {/if}
</SlidePanel>
