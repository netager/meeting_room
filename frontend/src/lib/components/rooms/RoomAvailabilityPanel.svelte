<script>
  import { getRoomSchedule } from '../../api/meetingRooms.js'
  import { showToast } from '../../stores/toast.js'

  let { roomId, initialDate = null } = $props()

  function todayStr() {
    const d = new Date()
    return d.toISOString().slice(0, 10)
  }

  let selectedDate = $state(initialDate || todayStr())
  let slots = $state([])
  let loading = $state(false)

  const HOUR_START = 8
  const HOUR_END = 20
  const SLOT_COUNT = (HOUR_END - HOUR_START) * 2

  const slotIndices = $derived(Array.from({ length: SLOT_COUNT }, (__, i) => i))

  function timeToMinutes(t) {
    const [h, m] = t.split(':').map(Number)
    return h * 60 + m
  }

  function slotIndex(minutesFromMidnight) {
    return Math.floor((minutesFromMidnight - HOUR_START * 60) / 30)
  }

  function formatHour(slotIdx) {
    const totalMinutes = HOUR_START * 60 + slotIdx * 30
    const h = Math.floor(totalMinutes / 60)
    const m = totalMinutes % 60
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  }

  let slotMap = $derived((() => {
    const map = new Array(SLOT_COUNT).fill(null)
    for (const s of slots) {
      const startMin = timeToMinutes(s.start_time)
      const endMin = timeToMinutes(s.end_time)
      const startIdx = Math.max(0, slotIndex(startMin))
      const endIdx = Math.min(SLOT_COUNT, slotIndex(endMin))
      for (let i = startIdx; i < endIdx; i++) {
        if (!map[i]) {
          map[i] = { ...s, isStart: i === startIdx }
        }
      }
    }
    return map
  })())

  function isPastSlot(slotIdx) {
    const now = new Date()
    const todayLocal = now.toISOString().slice(0, 10)
    if (selectedDate > todayLocal) return false
    if (selectedDate < todayLocal) return true
    const slotMinutes = HOUR_START * 60 + slotIdx * 30
    const nowMinutes = now.getHours() * 60 + now.getMinutes()
    return slotMinutes < nowMinutes
  }

  async function load() {
    if (!roomId) return
    loading = true
    try {
      slots = await getRoomSchedule(roomId, selectedDate)
    } catch (e) {
      showToast(e.message, 'error')
      slots = []
    } finally {
      loading = false
    }
  }

  function shiftDate(dateStr, deltaDays) {
    const [y, mo, d] = dateStr.split('-').map(Number)
    const ts = Date.UTC(y, mo - 1, d + deltaDays)
    const r = new Date(ts)
    return `${r.getUTCFullYear()}-${String(r.getUTCMonth() + 1).padStart(2, '0')}-${String(r.getUTCDate()).padStart(2, '0')}`
  }

  function prevDay() {
    selectedDate = shiftDate(selectedDate, -1)
  }

  function nextDay() {
    selectedDate = shiftDate(selectedDate, 1)
  }

  $effect(() => {
    if (roomId && selectedDate) load()
  })
</script>

<div class="space-y-3">
  <!-- Date navigation -->
  <div class="flex items-center gap-3">
    <button
      onclick={prevDay}
      class="rounded border border-neutral-700 text-neutral-300 hover:bg-[#1f1f1f] px-2 py-1 text-xs transition-colors"
    >
      ◀ 이전
    </button>
    <span class="text-sm text-white font-medium flex-1 text-center">{selectedDate}</span>
    <button
      onclick={nextDay}
      class="rounded border border-neutral-700 text-neutral-300 hover:bg-[#1f1f1f] px-2 py-1 text-xs transition-colors"
    >
      다음 ▶
    </button>
  </div>

  <!-- Timeline -->
  {#if loading}
    <div class="space-y-1">
      {#each Array.from({ length: 10 }, (__, i) => i) as i (i)}
        <div class="h-6 rounded bg-neutral-800 animate-pulse"></div>
      {/each}
    </div>
  {:else}
    <div class="space-y-0.5">
      {#each slotIndices as i (i)}
        {@const info = slotMap[i]}
        <div class="flex items-center gap-2">
          {#if i % 2 === 0}
            <span class="text-xs text-neutral-600 w-10 shrink-0">{formatHour(i)}</span>
          {:else}
            <span class="text-xs text-neutral-600 w-10 shrink-0"></span>
          {/if}
          {#if info}
            <div
              class="flex-1 h-5 rounded-sm bg-blue-500/30 border border-blue-500/40 px-1 overflow-hidden"
              title="{info.title} ({info.start_time}~{info.end_time})"
            >
              {#if info.isStart}
                <span class="text-xs text-blue-300 truncate block leading-5">{info.title}</span>
              {/if}
            </div>
          {:else}
            <div class="flex-1 h-5 rounded-sm {isPastSlot(i) ? 'bg-neutral-800/40' : 'bg-neutral-800/20'}"></div>
          {/if}
        </div>
      {/each}
    </div>
    {#if slots.length === 0}
      <p class="text-xs text-neutral-500 text-center">이 날짜에 예약된 회의가 없습니다.</p>
    {/if}
  {/if}
</div>
