<script>
  import { onMount, onDestroy } from 'svelte'
  import { get as storeGet } from 'svelte/store'
  import { currentUser } from '../lib/stores/auth.js'
  import { navigateTo } from '../router.js'
  import { showToast } from '../lib/stores/toast.js'
  import { listRooms } from '../lib/api/meetingRooms.js'
  import { searchEmployees } from '../lib/api/employees.js'
  import { createMeeting, updateMeeting, getMeeting, getFiles, uploadFile } from '../lib/api/meetings.js'
  import Modal from '../lib/components/common/Modal.svelte'
  import RoomAvailabilityPanel from '../lib/components/rooms/RoomAvailabilityPanel.svelte'
  import { generateUUID } from '../lib/utils/uuid.js'

  let { meetingId = null } = $props()

  const isEdit = !!meetingId

  // ── Form fields ────────────────────────────────────────────────
  let title = $state('')
  let roomId = $state('')
  let meetingDate = $state('')
  let startTime = $state('')
  let endTime = $state('')
  let agenda = $state('')

  // ── Attendees ──────────────────────────────────────────────────
  let attendees = $state([])
  let attendeeQuery = $state('')
  let attendeeResults = $state([])
  let showAttendeeDropdown = $state(false)
  let attendeeLoading = $state(false)
  let searchTimer = null

  // ── Files ──────────────────────────────────────────────────────
  const ALLOWED_EXT = new Set(['pdf','ppt','pptx','doc','docx','xls','xlsx','hwp','hwpx','png','jpg','jpeg','zip'])
  const MAX_SIZE_BYTES = 50 * 1024 * 1024

  let fileItems = $state([])
  let existingFiles = $state([])

  let isUploading = $derived(fileItems.some(f => f.status === 'uploading'))

  // ── UI state ───────────────────────────────────────────────────
  let rooms = $state([])
  let loading = $state(true)
  let submitting = $state(false)
  let isDirty = $state(false)

  let formError = $state('')
  let titleError = $state('')
  let roomError = $state('')
  let dateError = $state('')
  let timeError = $state('')

  let showLeaveModal = $state(false)
  let pendingNavTarget = $state(null)

  // ── Time slots ─────────────────────────────────────────────────
  function genSlots(fromH, fromM, toH, toM) {
    const result = []
    let h = fromH, m = fromM
    while (h * 60 + m <= toH * 60 + toM) {
      result.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
      m += 30
      if (m >= 60) { m -= 60; h++ }
    }
    return result
  }
  const START_TIMES = genSlots(7, 0, 22, 30)
  const END_TIMES = genSlots(7, 30, 23, 0)

  // ── clickOutside action ────────────────────────────────────────
  function clickOutside(node, handler) {
    function handle(e) {
      if (!node.contains(e.target)) handler()
    }
    document.addEventListener('click', handle, true)
    return { destroy() { document.removeEventListener('click', handle, true) } }
  }

  // ── Load ───────────────────────────────────────────────────────
  onMount(async () => {
    window.addEventListener('before-navigate', handleBeforeNavigate)
    window.addEventListener('beforeunload', handleBeforeUnload)

    try {
      rooms = await listRooms({ status: 'NORMAL' })
      if (!Array.isArray(rooms)) rooms = rooms.items || []
    } catch {
      showToast('회의실 목록을 불러오지 못했습니다.', 'error')
    }

    if (isEdit) {
      try {
        const [meeting, filesRes] = await Promise.all([
          getMeeting(meetingId),
          getFiles(meetingId),
        ])
        title = meeting.title || ''
        roomId = String(meeting.room_id || '')
        meetingDate = meeting.meeting_date || ''
        startTime = (meeting.start_time || '').slice(0, 5)
        endTime = (meeting.end_time || '').slice(0, 5)
        agenda = meeting.agenda || ''
        const creatorEmpNo = meeting.creator_emp_no
        attendees = (meeting.attendees || []).map(a => ({
          emp_no: a.emp_no,
          name: a.name,
          dept_name: a.dept_name || '',
          job_title: a.job_title || '',
          isCreator: a.emp_no === creatorEmpNo,
        }))
        const fr = filesRes
        existingFiles = Array.isArray(fr) ? fr : (fr.items || [])
      } catch (e) {
        showToast(e.message || '회의 정보를 불러오지 못했습니다.', 'error')
      }
    } else {
      const user = storeGet(currentUser)
      if (user) {
        attendees = [{
          emp_no: user.emp_no,
          name: user.name,
          dept_name: '',
          job_title: '',
          isCreator: true,
        }]
      }
    }

    loading = false
    isDirty = false
  })

  onDestroy(() => {
    window.removeEventListener('before-navigate', handleBeforeNavigate)
    window.removeEventListener('beforeunload', handleBeforeUnload)
    clearTimeout(searchTimer)
  })

  // ── Navigation guard ───────────────────────────────────────────
  function handleBeforeUnload(e) {
    if (isDirty || isUploading) { e.preventDefault(); e.returnValue = '' }
  }

  function handleBeforeNavigate(e) {
    if (isDirty || isUploading) {
      e.preventDefault()
      pendingNavTarget = e.detail.to
      showLeaveModal = true
    }
  }

  function confirmLeave() {
    isDirty = false
    showLeaveModal = false
    const target = pendingNavTarget
    pendingNavTarget = null
    if (target) window.location.hash = target
  }

  function cancelLeave() {
    showLeaveModal = false
    pendingNavTarget = null
  }

  // ── Attendee search ────────────────────────────────────────────
  function onAttendeeInput(e) {
    attendeeQuery = e.target.value
    clearTimeout(searchTimer)
    if (!attendeeQuery.trim()) {
      attendeeResults = []
      showAttendeeDropdown = false
      return
    }
    showAttendeeDropdown = true
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

  function addAttendee(emp) {
    if (!attendees.find(a => a.emp_no === emp.emp_no)) {
      attendees = [...attendees, {
        emp_no: emp.emp_no,
        name: emp.name,
        dept_name: emp.dept_name || '',
        job_title: emp.job_title || '',
        isCreator: false,
      }]
      isDirty = true
    }
    attendeeQuery = ''
    attendeeResults = []
    showAttendeeDropdown = false
  }

  function removeAttendee(empNo) {
    attendees = attendees.filter(a => a.emp_no !== empNo)
    isDirty = true
  }

  // ── File handling ──────────────────────────────────────────────
  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`
    return `${(bytes / 1024).toFixed(0)}KB`
  }

  function getExt(name) {
    return name.split('.').pop().toLowerCase()
  }

  function onFileInputChange(e) {
    addFiles(Array.from(e.target.files || []))
    e.target.value = ''
  }

  function onDrop(e) {
    e.preventDefault()
    addFiles(Array.from(e.dataTransfer.files || []))
  }

  function addFiles(files) {
    const newItems = files.map(file => {
      const ext = getExt(file.name)
      let status = 'pending'
      let error = ''
      if (!ALLOWED_EXT.has(ext)) {
        status = 'invalid'
        error = '허용되지 않는 파일 형식'
      } else if (file.size > MAX_SIZE_BYTES) {
        status = 'invalid'
        error = '파일 크기가 50MB를 초과합니다.'
      }
      return { id: generateUUID(), file, name: file.name, sizeStr: formatSize(file.size), progress: 0, status, error }
    })
    fileItems = [...fileItems, ...newItems]
    isDirty = true

    if (isEdit) {
      newItems.filter(f => f.status === 'pending').forEach(doUpload)
    }
  }

  async function doUpload(item) {
    if (!meetingId) return
    updateFileItem(item.id, { status: 'uploading' })
    try {
      const result = await uploadFile(meetingId, item.file, (pct) => {
        updateFileItem(item.id, { progress: pct })
      })
      updateFileItem(item.id, { status: 'done', progress: 100 })
      existingFiles = [...existingFiles, result]
    } catch (e) {
      updateFileItem(item.id, { status: 'error', error: e.message })
    }
  }

  function updateFileItem(id, patch) {
    fileItems = fileItems.map(f => f.id === id ? { ...f, ...patch } : f)
  }

  function removeFileItem(id) {
    fileItems = fileItems.filter(f => f.id !== id)
  }

  // ── Validation ─────────────────────────────────────────────────
  function validate() {
    let ok = true
    titleError = roomError = dateError = timeError = formError = ''

    if (!title.trim()) { titleError = '회의명을 입력하세요.'; ok = false }
    if (!roomId) { roomError = '회의실을 선택하세요.'; ok = false }
    if (!meetingDate) { dateError = '날짜를 선택하세요.'; ok = false }
    if (!startTime) { timeError = '시작 시간을 선택하세요.'; ok = false }
    else if (!endTime) { timeError = '종료 시간을 선택하세요.'; ok = false }
    else if (startTime >= endTime) { timeError = '종료 시간은 시작 시간보다 늦어야 합니다.'; ok = false }

    return ok
  }

  // ── Submit ─────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!validate()) return
    if (isUploading) { showToast('파일 업로드 중입니다. 완료 후 저장하세요.', 'warning'); return }

    submitting = true
    formError = ''
    try {
      const payload = {
        title: title.trim(),
        room_id: roomId,
        meeting_date: meetingDate,
        start_time: startTime,
        end_time: endTime,
        agenda: agenda.trim() || null,
        attendee_emp_nos: attendees.map(a => a.emp_no),
      }

      let savedId
      if (isEdit) {
        await updateMeeting(meetingId, payload)
        savedId = meetingId
      } else {
        const created = await createMeeting(payload)
        savedId = created.id

        // Upload staged files after meeting creation
        const toUpload = fileItems.filter(f => f.status === 'pending')
        for (const item of toUpload) {
          updateFileItem(item.id, { status: 'uploading' })
          try {
            await uploadFile(savedId, item.file, (pct) => updateFileItem(item.id, { progress: pct }))
            updateFileItem(item.id, { status: 'done', progress: 100 })
          } catch (e) {
            updateFileItem(item.id, { status: 'error', error: e.message })
          }
        }
      }

      isDirty = false
      showToast(isEdit ? '회의가 수정되었습니다.' : '회의가 신청되었습니다.')
      navigateTo(`#/meetings/${savedId}`)
    } catch (e) {
      if (e.code === 'ROOM_BOOKING_CONFLICT') {
        formError = '선택한 시간에 이미 예약이 있습니다. 다른 시간이나 회의실을 선택하세요.'
      } else {
        showToast(e.message || '저장에 실패했습니다.', 'error')
      }
    } finally {
      submitting = false
    }
  }

  function onStartTimeChange() {
    isDirty = true
    if (startTime && endTime && startTime >= endTime) {
      const [h, m] = startTime.split(':').map(Number)
      const newMin = h * 60 + m + 60
      const newH = Math.floor(newMin / 60)
      const newM = newMin % 60
      if (newH <= 23) {
        endTime = `${String(newH).padStart(2, '0')}:${String(newM).padStart(2, '0')}`
      } else {
        endTime = ''
      }
    }
  }

  function handleCancel() {
    isDirty = false
    navigateTo(isEdit ? `#/meetings/${meetingId}` : '#/meetings')
  }

  function openFileInput() {
    document.getElementById('meeting-file-input').click()
  }
</script>

<!-- Leave confirmation modal -->
<Modal title="저장하지 않은 내용" open={showLeaveModal} onClose={cancelLeave}>
  <p class="text-sm text-neutral-300">저장하지 않은 내용이 있습니다. 이 페이지를 떠나시겠습니까?</p>
  {#snippet footer()}
    <button
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
      onclick={cancelLeave}
      autofocus
    >
      취소
    </button>
    <button
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors"
      onclick={confirmLeave}
    >
      떠나기
    </button>
  {/snippet}
</Modal>

{#if loading}
  <div class="px-6 py-8 max-w-5xl space-y-4">
    <div class="h-8 w-48 rounded bg-neutral-800 animate-pulse"></div>
    {#each Array.from({ length: 5 }, (_, i) => i) as i (i)}
      <div class="h-12 rounded-lg bg-neutral-800 animate-pulse"></div>
    {/each}
  </div>
{:else}
  <div class="px-6 py-8 max-w-5xl">
    <h1 class="text-2xl font-semibold text-white mb-6">{isEdit ? '회의 수정' : '회의 신청'}</h1>

    <div class="flex gap-6 items-start">
      <!-- Left: form -->
      <div class="flex-1 space-y-5 min-w-0">

        <!-- Title -->
        <div>
          <label class="block text-sm font-medium text-neutral-300 mb-1.5">회의명 *</label>
          <input
            type="text"
            bind:value={title}
            oninput={() => isDirty = true}
            maxlength="200"
            placeholder="회의명을 입력하세요"
            class="w-full rounded-lg bg-neutral-900 border {titleError ? 'border-red-500' : 'border-neutral-800'} text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
          />
          {#if titleError}<p class="mt-1 text-xs text-red-400">{titleError}</p>{/if}
        </div>

        <!-- Room + Date -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-neutral-300 mb-1.5">회의실 *</label>
            <select
              bind:value={roomId}
              onchange={() => isDirty = true}
              class="w-full rounded-lg bg-neutral-900 border {roomError ? 'border-red-500' : 'border-neutral-800'} text-white px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
            >
              <option value="">회의실 선택</option>
              {#each rooms as room (room.id)}
                <option value={String(room.id)}>{room.name}</option>
              {/each}
            </select>
            {#if roomError}<p class="mt-1 text-xs text-red-400">{roomError}</p>{/if}
          </div>

          <div>
            <label class="block text-sm font-medium text-neutral-300 mb-1.5">날짜 *</label>
            <input
              type="date"
              bind:value={meetingDate}
              onchange={() => isDirty = true}
              class="w-full rounded-lg bg-neutral-900 border {dateError ? 'border-red-500' : 'border-neutral-800'} text-white px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
            />
            {#if dateError}<p class="mt-1 text-xs text-red-400">{dateError}</p>{/if}
          </div>
        </div>

        <!-- Start + End time -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-neutral-300 mb-1.5">시작 시간 *</label>
            <select
              bind:value={startTime}
              onchange={onStartTimeChange}
              class="w-full rounded-lg bg-neutral-900 border {timeError ? 'border-red-500' : 'border-neutral-800'} text-white px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
            >
              <option value="">선택</option>
              {#each START_TIMES as t (t)}
                <option value={t}>{t}</option>
              {/each}
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-neutral-300 mb-1.5">종료 시간 *</label>
            <select
              bind:value={endTime}
              onchange={() => isDirty = true}
              class="w-full rounded-lg bg-neutral-900 border {timeError ? 'border-red-500' : 'border-neutral-800'} text-white px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
            >
              <option value="">선택</option>
              {#each END_TIMES as t (t)}
                <option value={t} disabled={!!startTime && t <= startTime}>{t}</option>
              {/each}
            </select>
          </div>
        </div>
        {#if timeError}<p class="text-xs text-red-400">{timeError}</p>{/if}

        <!-- Attendees -->
        <div>
          <label class="block text-sm font-medium text-neutral-300 mb-1.5">참석자</label>
          <!-- Search with click-outside -->
          <div
            class="relative"
            use:clickOutside={() => { showAttendeeDropdown = false; attendeeResults = [] }}
          >
            <input
              type="text"
              value={attendeeQuery}
              oninput={onAttendeeInput}
              onfocus={() => { if (attendeeQuery.trim()) showAttendeeDropdown = true }}
              placeholder="이름 또는 행번으로 검색..."
              class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600"
            />
            {#if showAttendeeDropdown && (attendeeLoading || attendeeResults.length > 0 || (attendeeQuery.trim() && !attendeeLoading))}
              <div
                class="absolute z-20 left-0 right-0 mt-1 rounded-lg bg-[#1f1f1f] border border-neutral-700 max-h-52 overflow-y-auto shadow-lg"
                role="listbox"
              >
                {#if attendeeLoading}
                  <p class="px-4 py-3 text-sm text-neutral-500">검색 중...</p>
                {:else if attendeeResults.length === 0}
                  <p class="px-4 py-3 text-sm text-neutral-500">검색 결과 없음</p>
                {:else}
                  {#each attendeeResults.slice(0, 10) as emp (emp.emp_no)}
                    {@const alreadyAdded = attendees.some(a => a.emp_no === emp.emp_no)}
                    <button
                      type="button"
                      role="option"
                      aria-selected={alreadyAdded}
                      class="w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors {alreadyAdded ? 'opacity-40 cursor-not-allowed' : 'hover:bg-neutral-700 text-neutral-200 cursor-pointer'}"
                      disabled={alreadyAdded}
                      onclick={() => addAttendee(emp)}
                    >
                      <span class="font-medium">{emp.name}</span>
                      {#if emp.dept_name}<span class="text-neutral-500 text-xs">{emp.dept_name}</span>{/if}
                      {#if emp.job_title}<span class="text-neutral-500 text-xs">· {emp.job_title}</span>{/if}
                    </button>
                  {/each}
                {/if}
              </div>
            {/if}
          </div>

          <!-- Attendee chips -->
          {#if attendees.length > 0}
            <div class="flex flex-wrap gap-2 mt-2">
              {#each attendees as a (a.emp_no)}
                <span class="inline-flex items-center gap-1.5 rounded-md bg-neutral-800 border border-neutral-700 px-2.5 py-1 text-xs text-neutral-200">
                  <span class="font-medium">{a.name}</span>
                  {#if a.dept_name}<span class="text-neutral-500">({a.dept_name})</span>{/if}
                  {#if a.isCreator}
                    <span class="text-neutral-600 text-xs">🔒</span>
                  {:else}
                    <button
                      type="button"
                      class="text-neutral-500 hover:text-white transition-colors leading-none"
                      onclick={() => removeAttendee(a.emp_no)}
                      title="{a.name} 제거"
                    >✕</button>
                  {/if}
                </span>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Agenda -->
        <div>
          <label class="block text-sm font-medium text-neutral-300 mb-1.5">안건</label>
          <textarea
            bind:value={agenda}
            oninput={() => isDirty = true}
            maxlength="2000"
            rows="4"
            placeholder="회의 안건을 입력하세요 (선택)"
            class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600 resize-none"
          ></textarea>
          <p class="mt-1 text-xs text-neutral-600 text-right">{agenda.length}/2000</p>
        </div>

        <!-- File upload -->
        <div>
          <label class="block text-sm font-medium text-neutral-300 mb-1.5">첨부 파일</label>

          <!-- Drop zone -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="border-2 border-dashed border-neutral-700 rounded-lg px-4 py-6 text-center cursor-pointer hover:border-neutral-500 transition-colors"
            onclick={openFileInput}
            ondragover={(e) => e.preventDefault()}
            ondragenter={(e) => e.preventDefault()}
            ondrop={onDrop}
          >
            <p class="text-sm text-neutral-400">파일을 드래그하거나 클릭하여 추가</p>
            <p class="text-xs text-neutral-600 mt-1">PDF, PPT, DOC, XLS, HWP, PNG, JPG, ZIP · 최대 50MB</p>
          </div>
          <input
            id="meeting-file-input"
            type="file"
            multiple
            accept=".pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.hwp,.hwpx,.png,.jpg,.jpeg,.zip"
            class="hidden"
            onchange={onFileInputChange}
          />

          <!-- Staged / uploading files -->
          {#if fileItems.length > 0}
            <ul class="mt-2 space-y-1.5">
              {#each fileItems as f (f.id)}
                <li class="flex items-center gap-2 rounded-lg bg-neutral-900 border border-neutral-800 px-3 py-2">
                  {#if f.status === 'done'}
                    <span class="text-green-400 text-xs shrink-0">✅</span>
                  {:else if f.status === 'error' || f.status === 'invalid'}
                    <span class="text-red-400 text-xs shrink-0">❌</span>
                  {:else if f.status === 'uploading'}
                    <span class="text-blue-400 text-xs shrink-0">⬆</span>
                  {:else}
                    <span class="text-neutral-500 text-xs shrink-0">📄</span>
                  {/if}
                  <span class="text-sm text-neutral-300 flex-1 truncate min-w-0">{f.name}</span>
                  <span class="text-xs text-neutral-500 shrink-0">{f.sizeStr}</span>
                  {#if f.status === 'uploading'}
                    <div class="w-20 h-1.5 rounded-full bg-neutral-700 shrink-0">
                      <div class="h-full rounded-full bg-blue-500 transition-all" style="width: {f.progress}%"></div>
                    </div>
                    <span class="text-xs text-neutral-500 w-8 text-right shrink-0">{f.progress}%</span>
                  {:else if f.status === 'error' || f.status === 'invalid'}
                    <span class="text-xs text-red-400 shrink-0 truncate max-w-24" title={f.error}>{f.error}</span>
                  {/if}
                  <button
                    type="button"
                    class="text-neutral-500 hover:text-white text-xs shrink-0 transition-colors disabled:opacity-30"
                    onclick={() => removeFileItem(f.id)}
                    disabled={f.status === 'uploading'}
                    title="제거"
                  >✕</button>
                </li>
              {/each}
            </ul>
          {/if}

          <!-- Existing files (edit mode) -->
          {#if existingFiles.length > 0}
            <ul class="mt-2 space-y-1.5">
              {#each existingFiles as f (f.id)}
                <li class="flex items-center gap-2 rounded-lg bg-neutral-900 border border-neutral-800 px-3 py-2">
                  <span class="text-neutral-500 text-xs shrink-0">📎</span>
                  <span class="text-sm text-neutral-300 flex-1 truncate">{f.original_filename || f.filename || f.name || '파일'}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>

        <!-- Inline form error (booking conflict etc.) -->
        {#if formError}
          <div class="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
            <p class="text-sm text-red-400">{formError}</p>
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-3 pt-2 border-t border-neutral-800">
          <button
            type="button"
            class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
            onclick={handleCancel}
          >
            취소
          </button>
          <button
            type="button"
            class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleSubmit}
            disabled={submitting || isUploading}
          >
            {#if submitting}
              저장 중...
            {:else if isUploading}
              업로드 중...
            {:else if isEdit}
              수정 완료
            {:else}
              회의 신청
            {/if}
          </button>
        </div>
      </div>

      <!-- Right: availability panel -->
      <div class="w-60 shrink-0">
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-4 sticky top-8">
          <h3 class="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-3">회의실 가용 현황</h3>
          {#if roomId && meetingDate}
            {#if rooms.find(r => String(r.id) === roomId)}
              <p class="text-xs text-neutral-500 mb-3 truncate">{rooms.find(r => String(r.id) === roomId)?.name}</p>
            {/if}
            {#key roomId + '|' + meetingDate}
              <RoomAvailabilityPanel
                {roomId}
                controlledDate={meetingDate}
                selectedStart={startTime || null}
                selectedEnd={endTime || null}
              />
            {/key}
            <!-- Legend -->
            <div class="mt-4 space-y-1.5 border-t border-neutral-800 pt-3">
              <div class="flex items-center gap-2 text-xs text-neutral-500">
                <span class="w-3 h-3 rounded-sm bg-neutral-700/60 border border-neutral-600/40 shrink-0"></span>예약됨
              </div>
              <div class="flex items-center gap-2 text-xs text-neutral-500">
                <span class="w-3 h-3 rounded-sm bg-blue-500/30 border border-blue-500/40 shrink-0"></span>선택한 시간
              </div>
              <div class="flex items-center gap-2 text-xs text-neutral-500">
                <span class="w-3 h-3 rounded-sm bg-red-500/40 border border-red-500/50 shrink-0"></span>충돌
              </div>
            </div>
          {:else}
            <p class="text-xs text-neutral-600 leading-relaxed">회의실과 날짜를 선택하면<br>가용 시간을 확인할 수 있습니다.</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
