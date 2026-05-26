<script>
  import { onMount } from 'svelte'
  import Modal from '../common/Modal.svelte'
  import { createRoom, updateRoom, createEquipment, deleteEquipment } from '../../api/meetingRooms.js'
  import { listDepartments } from '../../api/departments.js'
  import { showToast } from '../../stores/toast.js'
  import { currentUser } from '../../stores/auth.js'

  let {
    mode = 'create',  // 'create' | 'edit'
    room = null,      // existing room data for edit mode
    open = false,
    onClose,
    onSave,
  } = $props()

  let departments = $state([])
  let saving = $state(false)

  let form = $state({
    name: '',
    location: '',
    dept_code: '',
    status: 'NORMAL',
  })

  let errors = $state({})

  // Equipment state (edit mode only)
  let newEqForm = $state({ name: '', quantity: 1, note: '' })
  let newEqError = $state('')
  let addingEq = $state(false)
  let deletingEqId = $state(null)
  let localEquipment = $state([])

  onMount(async () => {
    try {
      departments = await listDepartments()
    } catch {
      departments = []
    }
  })

  $effect(() => {
    if (open) {
      errors = {}
      newEqError = ''
      newEqForm = { name: '', quantity: 1, note: '' }
      if (mode === 'edit' && room) {
        form = {
          name: room.name,
          location: room.location,
          dept_code: room.dept_code,
          status: room.status,
        }
        localEquipment = [...(room.equipment ?? [])]
      } else {
        form = { name: '', location: '', dept_code: departments[0]?.code ?? '', status: 'NORMAL' }
        localEquipment = []
      }
    }
  })

  function validate() {
    const e = {}
    if (!form.name.trim()) e.name = '회의실명을 입력하세요.'
    else if (form.name.length > 100) e.name = '회의실명은 100자 이하여야 합니다.'
    if (!form.location.trim()) e.location = '위치를 입력하세요.'
    else if (form.location.length > 200) e.location = '위치는 200자 이하여야 합니다.'
    if (!form.dept_code) e.dept_code = '담당 부서를 선택하세요.'
    return e
  }

  async function handleSave() {
    errors = validate()
    if (Object.keys(errors).length > 0) return

    // UX guard: room_manager cannot set CLOSED
    if (form.status === 'CLOSED' && !$currentUser?.is_admin) {
      showToast('폐쇄 상태는 관리자만 변경할 수 있습니다.', 'warning')
      return
    }

    saving = true
    try {
      if (mode === 'create') {
        await createRoom({ name: form.name, location: form.location, dept_code: form.dept_code })
        showToast('회의실이 생성되었습니다.')
      } else {
        const payload = {
          name: form.name,
          location: form.location,
          dept_code: form.dept_code,
          status: form.status,
        }
        const result = await updateRoom(room.id, payload)
        if (result.warnings && result.warnings.length > 0) {
          for (const w of result.warnings) {
            showToast(w, 'warning')
          }
        } else {
          showToast('회의실이 수정되었습니다.')
        }
      }
      onSave?.()
      onClose?.()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      saving = false
    }
  }

  async function handleAddEquipment() {
    newEqError = ''
    if (!newEqForm.name.trim()) {
      newEqError = '집기명을 입력하세요.'
      return
    }
    const qty = Number(newEqForm.quantity)
    if (!qty || qty < 1) {
      newEqError = '수량은 1 이상이어야 합니다.'
      return
    }
    addingEq = true
    try {
      const eq = await createEquipment(room.id, {
        name: newEqForm.name.trim(),
        quantity: qty,
        note: newEqForm.note.trim() || null,
      })
      localEquipment = [...localEquipment, eq]
      newEqForm = { name: '', quantity: 1, note: '' }
      showToast('집기가 추가되었습니다.')
    } catch (e) {
      if (e.code === 'CONFLICT' || e.status === 409) {
        showToast('이미 등록된 집기 이름입니다.', 'error')
      } else {
        showToast(e.message, 'error')
      }
    } finally {
      addingEq = false
    }
  }

  async function handleDeleteEquipment(eqId) {
    deletingEqId = eqId
    try {
      await deleteEquipment(room.id, eqId)
      localEquipment = localEquipment.filter((e) => e.id !== eqId)
      showToast('집기가 삭제되었습니다.')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deletingEqId = null
    }
  }

  function onStatusChange(e) {
    const val = e.target.value
    if (val === 'CLOSED' && !$currentUser?.is_admin) {
      showToast('폐쇄 상태는 관리자만 설정할 수 있습니다.', 'warning')
      form.status = room?.status ?? 'NORMAL'
      return
    }
    form.status = val
  }
</script>

<Modal
  title={mode === 'create' ? '회의실 추가' : '회의실 수정'}
  open={open}
  onClose={onClose}
>
  <div class="space-y-4">
    <!-- Name -->
    <div>
      <label class="text-sm font-medium text-neutral-300 block mb-1">이름 <span class="text-red-400">*</span></label>
      <input
        type="text"
        bind:value={form.name}
        maxlength="100"
        placeholder="회의실명"
        class="w-full rounded-lg bg-neutral-900 border {errors.name ? 'border-red-500' : 'border-neutral-800'} text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
      />
      {#if errors.name}
        <p class="text-xs text-red-400 mt-1">{errors.name}</p>
      {/if}
    </div>

    <!-- Location -->
    <div>
      <label class="text-sm font-medium text-neutral-300 block mb-1">위치 <span class="text-red-400">*</span></label>
      <input
        type="text"
        bind:value={form.location}
        maxlength="200"
        placeholder="예: 본관 3층 서쪽"
        class="w-full rounded-lg bg-neutral-900 border {errors.location ? 'border-red-500' : 'border-neutral-800'} text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
      />
      {#if errors.location}
        <p class="text-xs text-red-400 mt-1">{errors.location}</p>
      {/if}
    </div>

    <!-- Department -->
    <div>
      <label class="text-sm font-medium text-neutral-300 block mb-1">담당 부서 <span class="text-red-400">*</span></label>
      <select
        bind:value={form.dept_code}
        class="w-full rounded-lg bg-neutral-900 border {errors.dept_code ? 'border-red-500' : 'border-neutral-800'} text-neutral-300 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
      >
        <option value="">부서 선택</option>
        {#each departments as d (d.code)}
          <option value={d.code}>{d.name} ({d.code})</option>
        {/each}
      </select>
      {#if errors.dept_code}
        <p class="text-xs text-red-400 mt-1">{errors.dept_code}</p>
      {/if}
    </div>

    <!-- Status (edit mode only) -->
    {#if mode === 'edit'}
      <div>
        <label class="text-sm font-medium text-neutral-300 block mb-1">상태</label>
        <select
          value={form.status}
          onchange={onStatusChange}
          class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
        >
          <option value="NORMAL">정상</option>
          <option value="TEMP_CLOSED">임시폐쇄</option>
          <option value="CLOSED" disabled={!$currentUser?.is_admin}>폐쇄{!$currentUser?.is_admin ? ' (admin 전용)' : ''}</option>
        </select>
      </div>

      <!-- Equipment management -->
      <div>
        <p class="text-xs text-neutral-500 uppercase tracking-wider mb-2">집기 관리</p>

        {#if localEquipment.length > 0}
          <div class="rounded-lg border border-neutral-800 overflow-hidden mb-3">
            <table class="w-full text-sm">
              <thead>
                <tr>
                  {#each ['집기명', '수량', '비고', ''] as h (h)}
                    <th class="px-3 py-2 text-left border-b border-neutral-800 text-xs text-neutral-500">{h}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each localEquipment as eq (eq.id)}
                  <tr class="border-b border-neutral-800/50">
                    <td class="px-3 py-2 text-neutral-300">{eq.name}</td>
                    <td class="px-3 py-2 text-neutral-400">{eq.quantity}</td>
                    <td class="px-3 py-2 text-neutral-500">{eq.note ?? '—'}</td>
                    <td class="px-3 py-2">
                      <button
                        onclick={() => handleDeleteEquipment(eq.id)}
                        disabled={deletingEqId === eq.id}
                        class="text-xs text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
                      >
                        {deletingEqId === eq.id ? '삭제 중...' : '삭제'}
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}

        <!-- Add equipment inline form -->
        <div class="rounded-lg border border-neutral-800 p-3 space-y-2">
          <p class="text-xs text-neutral-500">집기 추가</p>
          <div class="flex gap-2 flex-wrap">
            <input
              type="text"
              bind:value={newEqForm.name}
              placeholder="집기명"
              class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1.5 text-sm focus:outline-none focus:border-neutral-600 flex-1 min-w-24"
            />
            <input
              type="number"
              bind:value={newEqForm.quantity}
              min="1"
              placeholder="수량"
              class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1.5 text-sm focus:outline-none focus:border-neutral-600 w-20"
            />
            <input
              type="text"
              bind:value={newEqForm.note}
              placeholder="비고 (선택)"
              class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1.5 text-sm focus:outline-none focus:border-neutral-600 flex-1 min-w-24"
            />
            <button
              onclick={handleAddEquipment}
              disabled={addingEq}
              class="rounded bg-white text-black text-xs font-medium px-3 py-1.5 hover:bg-neutral-200 transition-colors disabled:opacity-50 shrink-0"
            >
              {addingEq ? '추가 중...' : '추가'}
            </button>
          </div>
          {#if newEqError}
            <p class="text-xs text-red-400">{newEqError}</p>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button
      onclick={onClose}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      취소
    </button>
    <button
      onclick={handleSave}
      disabled={saving}
      class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
    >
      {saving ? '저장 중...' : mode === 'create' ? '회의실 추가' : '수정 저장'}
    </button>
  {/snippet}
</Modal>
