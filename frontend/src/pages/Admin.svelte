<script>
  import { onMount } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { currentUser } from '../lib/stores/auth.js'
  import { navigateTo } from '../router.js'
  import { showToast } from '../lib/stores/toast.js'
  import * as employeesApi from '../lib/api/employees.js'
  import * as departmentsApi from '../lib/api/departments.js'
  import * as adminApi from '../lib/api/admin.js'
  import Table from '../lib/components/common/Table.svelte'
  import Pagination from '../lib/components/common/Pagination.svelte'
  import Modal from '../lib/components/common/Modal.svelte'
  import Badge from '../lib/components/common/Badge.svelte'
  import SlidePanel from '../lib/components/common/SlidePanel.svelte'
  import SkeletonTable from '../lib/components/common/SkeletonTable.svelte'

  // ── Tabs ──────────────────────────────────────────────────────────────────────
  let activeTab = $state('employees')

  // ── Employees ─────────────────────────────────────────────────────────────────
  let empData = $state({ items: [], total: 0, page: 1, size: 20, pages: 0 })
  let empFilters = $state({ status: '', search: '' })
  let empLoading = $state(true)

  let panelOpen = $state(false)
  let selectedEmp = $state(null)
  let empEditForm = $state({ name: '', dept_code: '', team_code: '', rank: '' })
  let permForm = $state({ is_admin: false, is_room_manager: false })
  let updateLoading = $state(false)

  let retireModal = $state(false)
  let retireLoading = $state(false)

  // Permission confirmation modal
  let permConfirmModal = $state({ open: false, field: '', newValue: false })

  // ── Departments ───────────────────────────────────────────────────────────────
  let departments = $state([])
  let deptTeams = $state({})
  let expandedDepts = new SvelteSet()
  let deptLoading = $state(false)

  let showNewDeptForm = $state(false)
  let newDeptForm = $state({ code: '', name: '' })
  let deptFormLoading = $state(false)

  let editingDept = $state(null)
  let editDeptForm = $state({ name: '' })

  let showNewTeamForm = $state({})
  let newTeamForm = $state({})
  let editingTeam = $state(null)
  let editTeamForm = $state({ name: '' })

  let deleteModal = $state({ open: false, type: '', item: null, loading: false })

  // ── ETL / Sync ────────────────────────────────────────────────────────────────
  let syncLogs = $state([])
  let syncLogsLoading = $state(false)
  let syncRunning = $state(false)

  let stagingData = $state([])
  let stagingLoading = $state(false)
  let showStagingSection = $state(false)

  let showNewStagingForm = $state(false)
  let newStagingForm = $state({ emp_no: '', name: '', dept_code: '', team_code: '', rank: '' })
  let stagingFormLoading = $state(false)

  let allDepts = $state([])

  // ── Audit Logs ────────────────────────────────────────────────────────────────
  let auditData = $state({ items: [], total: 0, page: 1, size: 20, pages: 0 })
  let auditFilters = $state({ action: '', resource_type: '', actor_emp_no: '', date_from: '', date_to: '' })
  let auditLoading = $state(false)
  let auditDetailLog = $state(null)
  let auditDetailOpen = $state(false)

  // ── Table headers ─────────────────────────────────────────────────────────────
  const empHeaders = [
    { key: 'emp_no', label: '행번' },
    { key: 'name', label: '이름' },
    { key: 'dept_code', label: '부서' },
    { key: 'rank', label: '직급' },
    { key: 'status', label: '재직 상태' },
    { key: 'permissions', label: '권한' },
  ]

  const auditHeaders = [
    { key: 'created_at', label: '시각' },
    { key: 'action', label: '액션' },
    { key: 'resource_type', label: '리소스' },
    { key: 'resource_id', label: '리소스 ID' },
    { key: 'actor', label: '수행자' },
    { key: 'ip_address', label: 'IP' },
  ]

  // ── Lifecycle ─────────────────────────────────────────────────────────────────
  onMount(async () => {
    if (!$currentUser?.is_admin) {
      navigateTo('#/')
      return
    }
    await Promise.all([loadEmployees(), loadDepartments(), loadAllDepts()])
  })

  // ── Employee functions ─────────────────────────────────────────────────────────
  async function loadEmployees(page = 1) {
    empLoading = true
    try {
      const result = await employeesApi.listEmployees({
        page,
        size: 20,
        status: empFilters.status || undefined,
        search: empFilters.search || undefined,
      })
      empData = result
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      empLoading = false
    }
  }

  function openEmployeePanel(emp) {
    selectedEmp = emp
    empEditForm = {
      name: emp.name,
      dept_code: emp.dept_code,
      team_code: emp.team_code ?? '',
      rank: emp.rank ?? '',
    }
    permForm = { is_admin: emp.is_admin, is_room_manager: emp.is_room_manager }
    panelOpen = true
  }

  async function handleUpdateEmployee() {
    if (!selectedEmp) return
    updateLoading = true
    try {
      await employeesApi.updateEmployee(selectedEmp.emp_no, {
        name: empEditForm.name || undefined,
        dept_code: empEditForm.dept_code || undefined,
        team_code: empEditForm.team_code || null,
        rank: empEditForm.rank || null,
      })
      showToast('직원 정보가 수정되었습니다.')
      panelOpen = false
      await loadEmployees(empData.page)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      updateLoading = false
    }
  }

  function handlePermToggle(field, newValue) {
    // UX-level self-check (backend also returns 403)
    if (selectedEmp?.emp_no === $currentUser?.emp_no) {
      showToast('자신의 권한은 변경할 수 없습니다.', 'error')
      return
    }
    permConfirmModal = { open: true, field, newValue }
  }

  async function handleUpdatePermissions() {
    if (!selectedEmp) return
    updateLoading = true
    const newPerms = { ...permForm, [permConfirmModal.field]: permConfirmModal.newValue }
    try {
      await employeesApi.updatePermissions(selectedEmp.emp_no, {
        is_admin: newPerms.is_admin,
        is_room_manager: newPerms.is_room_manager,
      })
      permForm = newPerms
      showToast('권한이 변경되었습니다.')
      permConfirmModal = { open: false, field: '', newValue: false }
      await loadEmployees(empData.page)
    } catch (e) {
      showToast(e.message, 'error')
      permConfirmModal = { open: false, field: '', newValue: false }
    } finally {
      updateLoading = false
    }
  }

  async function handleRetire() {
    if (!selectedEmp) return
    retireLoading = true
    try {
      await employeesApi.retireEmployee(selectedEmp.emp_no)
      showToast('퇴직 처리되었습니다.')
      retireModal = false
      panelOpen = false
      await loadEmployees(empData.page)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      retireLoading = false
    }
  }

  let searchTimeout = null
  function onSearchInput() {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => loadEmployees(1), 300)
  }

  // ── Department functions ───────────────────────────────────────────────────────
  async function loadDepartments() {
    deptLoading = true
    try {
      departments = await departmentsApi.listDepartments(true)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deptLoading = false
    }
  }

  async function loadAllDepts() {
    try {
      allDepts = await departmentsApi.listDepartments(false)
    } catch {
      // ignore
    }
  }

  async function toggleDept(code) {
    if (expandedDepts.has(code)) {
      expandedDepts.delete(code)
    } else {
      if (!deptTeams[code]) {
        try {
          deptTeams[code] = await departmentsApi.listTeams(code)
        } catch {
          deptTeams[code] = []
        }
      }
      expandedDepts.add(code)
    }
  }

  async function handleCreateDept() {
    if (!newDeptForm.code || !newDeptForm.name) return
    deptFormLoading = true
    try {
      await departmentsApi.createDepartment({ code: newDeptForm.code, name: newDeptForm.name })
      showToast('부서가 생성되었습니다.')
      newDeptForm = { code: '', name: '' }
      showNewDeptForm = false
      await loadDepartments()
      await loadAllDepts()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deptFormLoading = false
    }
  }

  async function handleUpdateDept(code) {
    if (!editDeptForm.name) return
    deptFormLoading = true
    try {
      await departmentsApi.updateDepartment(code, { name: editDeptForm.name })
      showToast('부서가 수정되었습니다.')
      editingDept = null
      await loadDepartments()
      await loadAllDepts()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deptFormLoading = false
    }
  }

  async function handleDeleteDept() {
    if (!deleteModal.item) return
    deleteModal.loading = true
    try {
      await departmentsApi.deleteDepartment(deleteModal.item.code)
      showToast('부서가 삭제되었습니다.')
      deleteModal = { open: false, type: '', item: null, loading: false }
      await loadDepartments()
      await loadAllDepts()
    } catch (e) {
      showToast(e.message, 'error')
      deleteModal.loading = false
    }
  }

  async function handleCreateTeam(deptCode) {
    const form = newTeamForm[deptCode]
    if (!form?.code || !form?.name) return
    deptFormLoading = true
    try {
      await departmentsApi.createTeam({ code: form.code, name: form.name, dept_code: deptCode })
      showToast('팀이 생성되었습니다.')
      showNewTeamForm = { ...showNewTeamForm, [deptCode]: false }
      newTeamForm = { ...newTeamForm, [deptCode]: { code: '', name: '' } }
      deptTeams[deptCode] = await departmentsApi.listTeams(deptCode)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deptFormLoading = false
    }
  }

  async function handleUpdateTeam(code, deptCode) {
    if (!editTeamForm.name) return
    deptFormLoading = true
    try {
      await departmentsApi.updateTeam(code, { name: editTeamForm.name })
      showToast('팀이 수정되었습니다.')
      editingTeam = null
      deptTeams[deptCode] = await departmentsApi.listTeams(deptCode)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      deptFormLoading = false
    }
  }

  async function handleDeleteTeam() {
    if (!deleteModal.item) return
    deleteModal.loading = true
    try {
      await departmentsApi.deleteTeam(deleteModal.item.code)
      showToast('팀이 삭제되었습니다.')
      const deptCode = deleteModal.item.dept_code
      deleteModal = { open: false, type: '', item: null, loading: false }
      if (deptCode) deptTeams[deptCode] = await departmentsApi.listTeams(deptCode)
    } catch (e) {
      showToast(e.message, 'error')
      deleteModal.loading = false
    }
  }

  // ── Sync / ETL functions ───────────────────────────────────────────────────────
  async function loadSyncLogs() {
    syncLogsLoading = true
    try {
      const result = await adminApi.getAuditLogs({ action: 'BATCH_RUN', size: 5 })
      syncLogs = result.items ?? []
    } catch {
      syncLogs = []
    } finally {
      syncLogsLoading = false
    }
  }

  async function loadStaging() {
    stagingLoading = true
    try {
      stagingData = await adminApi.listStaging()
      showStagingSection = true
    } catch (e) {
      if (e.code === 'FORBIDDEN') {
        showStagingSection = false
      } else {
        showToast(e.message, 'error')
      }
    } finally {
      stagingLoading = false
    }
  }

  async function handleRunSync() {
    syncRunning = true
    try {
      const result = await adminApi.runSync()
      showToast(
        `동기화 완료: 신규 ${result.created ?? 0}명, 변경 ${result.updated ?? 0}명, 퇴직 ${result.retired ?? 0}명`,
        'success'
      )
      await loadSyncLogs()
      if (showStagingSection) await loadStaging()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      syncRunning = false
    }
  }

  async function handleDeleteStaging(empNo) {
    try {
      await adminApi.deleteStaging(empNo)
      stagingData = stagingData.filter((r) => r.emp_no !== empNo)
      showToast('스테이징 레코드가 삭제되었습니다.')
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  async function handleUpsertStaging() {
    if (!newStagingForm.emp_no || !newStagingForm.name || !newStagingForm.dept_code) return
    stagingFormLoading = true
    try {
      await adminApi.upsertStaging({
        emp_no: newStagingForm.emp_no,
        name: newStagingForm.name,
        dept_code: newStagingForm.dept_code,
        team_code: newStagingForm.team_code || null,
        rank: newStagingForm.rank || null,
      })
      showToast('스테이징 레코드가 저장되었습니다.')
      newStagingForm = { emp_no: '', name: '', dept_code: '', team_code: '', rank: '' }
      showNewStagingForm = false
      await loadStaging()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      stagingFormLoading = false
    }
  }

  // ── Audit Log functions ────────────────────────────────────────────────────────
  async function loadAuditLogs(page = 1) {
    auditLoading = true
    try {
      const result = await adminApi.getAuditLogs({
        action: auditFilters.action || undefined,
        resource_type: auditFilters.resource_type || undefined,
        actor_emp_no: auditFilters.actor_emp_no || undefined,
        date_from: auditFilters.date_from || undefined,
        date_to: auditFilters.date_to || undefined,
        page,
        size: 20,
      })
      auditData = result
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      auditLoading = false
    }
  }

  function openAuditDetail(log) {
    auditDetailLog = log
    auditDetailOpen = true
  }

  function onTabChange(tab) {
    activeTab = tab
    if (tab === 'sync' && syncLogs.length === 0) {
      loadSyncLogs()
      loadStaging()
    }
    if (tab === 'audit' && auditData.items.length === 0) {
      loadAuditLogs(1)
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function statusVariant(status) {
    return status === 'ACTIVE' ? 'success' : 'neutral'
  }

  function statusLabel(status) {
    return status === 'ACTIVE' ? '재직' : '퇴직'
  }

  function formatSyncDetail(detail) {
    if (!detail) return '정보 없음'
    return detail
  }

  function formatDateTime(dt) {
    if (!dt) return '—'
    return dt.slice(0, 19).replace('T', ' ')
  }

  function permConfirmLabel() {
    const name = selectedEmp?.name ?? ''
    const field = permConfirmModal.field
    const permName = field === 'is_admin' ? '관리자' : '회의실 담당자'
    const action = permConfirmModal.newValue ? '부여' : '해제'
    return `${name}의 ${permName} 권한을 ${action}하시겠습니까?`
  }
</script>

<div class="px-6 py-8 max-w-5xl">
  <!-- Page header -->
  <div class="flex items-center justify-between mb-8">
    <h1 class="text-2xl font-semibold text-white">관리자 메뉴</h1>
  </div>

  <!-- Tabs -->
  <div class="flex gap-1 mb-6 border-b border-neutral-800">
    {#each [['employees', '직원 관리'], ['departments', '부서·팀 관리'], ['sync', 'ETL 동기화'], ['audit', '감사 로그']] as [tab, label] (tab)}
      <button
        onclick={() => onTabChange(tab)}
        class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === tab
          ? 'border-white text-white'
          : 'border-transparent text-neutral-400 hover:text-neutral-200'}"
      >
        {label}
      </button>
    {/each}
  </div>

  <!-- ── Tab: 직원 관리 ──────────────────────────────────────────────────────── -->
  {#if activeTab === 'employees'}
    <div class="space-y-4">
      <!-- Filters -->
      <div class="flex items-center gap-3">
        <select
          bind:value={empFilters.status}
          onchange={() => loadEmployees(1)}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
        >
          <option value="">전체</option>
          <option value="ACTIVE">재직</option>
          <option value="RETIRED">퇴직</option>
        </select>
        <input
          type="text"
          bind:value={empFilters.search}
          oninput={onSearchInput}
          placeholder="이름 검색..."
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-2 text-sm focus:outline-none focus:border-neutral-600 w-56"
        />
      </div>

      <!-- Table -->
      <div class="rounded-lg bg-[#141414] border border-neutral-800">
        {#if empLoading}
          <SkeletonTable rows={5} cols={6} />
        {:else}
          <Table
            headers={empHeaders}
            rows={empData.items}
            onRowClick={openEmployeePanel}
          >
            {#snippet cell(row, col)}
              {#if col.key === 'status'}
                <Badge text={statusLabel(row.status)} variant={statusVariant(row.status)} />
              {:else if col.key === 'permissions'}
                <div class="flex gap-1 flex-wrap">
                  {#if row.is_admin}
                    <Badge text="admin" variant="warning" />
                  {/if}
                  {#if row.is_room_manager}
                    <Badge text="room_mgr" variant="neutral" />
                  {/if}
                </div>
              {:else}
                {row[col.key] ?? '—'}
              {/if}
            {/snippet}
            {#snippet empty()}
              <tr>
                <td colspan="6" class="px-4 py-8 text-center text-neutral-500">
                  조회 조건에 맞는 직원이 없습니다.
                </td>
              </tr>
            {/snippet}
          </Table>
          <div class="px-4">
            <Pagination
              page={empData.page}
              pages={empData.pages}
              total={empData.total}
              onPageChange={(p) => loadEmployees(p)}
            />
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- ── Tab: 부서·팀 관리 ───────────────────────────────────────────────────── -->
  {#if activeTab === 'departments'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          onclick={() => { showNewDeptForm = !showNewDeptForm }}
          class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
        >
          + 부서 추가
        </button>
      </div>

      {#if showNewDeptForm}
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-4 flex items-center gap-3">
          <input
            type="text"
            bind:value={newDeptForm.code}
            placeholder="부서코드"
            class="rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600 w-32"
          />
          <input
            type="text"
            bind:value={newDeptForm.name}
            placeholder="부서명"
            class="rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600 w-48"
          />
          <button
            onclick={handleCreateDept}
            disabled={deptFormLoading}
            class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
          >
            {deptFormLoading ? '저장 중...' : '저장'}
          </button>
          <button
            onclick={() => { showNewDeptForm = false }}
            class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
          >
            취소
          </button>
        </div>
      {/if}

      {#if deptLoading}
        <div class="text-neutral-500 text-sm py-4">로딩 중...</div>
      {:else if departments.length === 0}
        <div class="rounded-lg bg-[#141414] border border-neutral-800 px-4 py-8 text-center text-neutral-500">
          등록된 부서가 없습니다.
        </div>
      {:else}
        <div class="rounded-lg bg-[#141414] border border-neutral-800 divide-y divide-neutral-800">
          {#each departments as dept (dept.code)}
            <div>
              <!-- Department row -->
              <div class="flex items-center gap-3 px-4 py-3 hover:bg-[#1f1f1f] transition-colors">
                <button
                  onclick={() => toggleDept(dept.code)}
                  class="text-neutral-400 hover:text-white text-xs w-4"
                >
                  {expandedDepts.has(dept.code) ? '▼' : '▶'}
                </button>

                {#if editingDept === dept.code}
                  <input
                    type="text"
                    bind:value={editDeptForm.name}
                    class="rounded bg-neutral-900 border border-neutral-700 text-white px-2 py-1 text-sm focus:outline-none focus:border-neutral-600 w-40"
                  />
                  <button
                    onclick={() => handleUpdateDept(dept.code)}
                    class="text-xs text-green-400 hover:text-green-300 transition-colors"
                  >
                    저장
                  </button>
                  <button
                    onclick={() => { editingDept = null }}
                    class="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
                  >
                    취소
                  </button>
                {:else}
                  <span class="text-white text-sm font-medium flex-1">{dept.name}</span>
                  <span class="text-neutral-500 text-xs">{dept.code}</span>
                  <Badge
                    text={dept.status === 'ACTIVE' ? '활성' : '비활성'}
                    variant={dept.status === 'ACTIVE' ? 'success' : 'neutral'}
                  />
                  <button
                    onclick={() => { editingDept = dept.code; editDeptForm = { name: dept.name } }}
                    class="text-xs text-neutral-400 hover:text-white transition-colors ml-2"
                  >
                    수정
                  </button>
                  <button
                    onclick={() => { deleteModal = { open: true, type: 'dept', item: dept, loading: false } }}
                    class="text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    삭제
                  </button>
                {/if}
              </div>

              <!-- Teams (expanded) -->
              {#if expandedDepts.has(dept.code)}
                <div class="bg-[#0f0f0f] pl-8 pr-4 py-2 space-y-1">
                  {#if deptTeams[dept.code]}
                    {#each deptTeams[dept.code] as team (team.code)}
                      <div class="flex items-center gap-3 py-2 border-b border-neutral-800/50 last:border-0">
                        {#if editingTeam === team.code}
                          <input
                            type="text"
                            bind:value={editTeamForm.name}
                            class="rounded bg-neutral-900 border border-neutral-700 text-white px-2 py-1 text-sm focus:outline-none focus:border-neutral-600 w-36"
                          />
                          <button
                            onclick={() => handleUpdateTeam(team.code, dept.code)}
                            class="text-xs text-green-400 hover:text-green-300 transition-colors"
                          >
                            저장
                          </button>
                          <button
                            onclick={() => { editingTeam = null }}
                            class="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
                          >
                            취소
                          </button>
                        {:else}
                          <span class="text-neutral-300 text-sm flex-1">{team.name}</span>
                          <span class="text-neutral-600 text-xs">{team.code}</span>
                          <button
                            onclick={() => { editingTeam = team.code; editTeamForm = { name: team.name } }}
                            class="text-xs text-neutral-400 hover:text-white transition-colors"
                          >
                            수정
                          </button>
                          <button
                            onclick={() => { deleteModal = { open: true, type: 'team', item: team, loading: false } }}
                            class="text-xs text-red-400 hover:text-red-300 transition-colors"
                          >
                            삭제
                          </button>
                        {/if}
                      </div>
                    {/each}
                  {/if}

                  <!-- Add team inline form -->
                  {#if showNewTeamForm[dept.code]}
                    <div class="flex items-center gap-2 py-2">
                      <input
                        type="text"
                        bind:value={newTeamForm[dept.code].code}
                        placeholder="팀코드"
                        class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-24"
                      />
                      <input
                        type="text"
                        bind:value={newTeamForm[dept.code].name}
                        placeholder="팀명"
                        class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-36"
                      />
                      <button
                        onclick={() => handleCreateTeam(dept.code)}
                        class="text-xs text-green-400 hover:text-green-300 transition-colors"
                      >
                        저장
                      </button>
                      <button
                        onclick={() => { showNewTeamForm = { ...showNewTeamForm, [dept.code]: false } }}
                        class="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
                      >
                        취소
                      </button>
                    </div>
                  {:else}
                    <button
                      onclick={() => {
                        showNewTeamForm = { ...showNewTeamForm, [dept.code]: true }
                        newTeamForm = { ...newTeamForm, [dept.code]: { code: '', name: '' } }
                      }}
                      class="text-xs text-neutral-500 hover:text-neutral-400 transition-colors py-1"
                    >
                      + 팀 추가
                    </button>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- ── Tab: ETL 동기화 ────────────────────────────────────────────────────── -->
  {#if activeTab === 'sync'}
    <div class="space-y-6">
      <!-- Run sync -->
      <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-sm font-medium text-white">직원원장 동기화</h3>
            <p class="text-xs text-neutral-500 mt-1">임시원장(스테이징) 데이터를 직원원장에 반영합니다.</p>
          </div>
          <button
            onclick={handleRunSync}
            disabled={syncRunning}
            class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
          >
            {syncRunning ? '실행 중...' : '동기화 즉시 실행'}
          </button>
        </div>

        <!-- Last sync logs -->
        <div>
          <p class="text-xs text-neutral-500 uppercase tracking-wider mb-2">최근 동기화 이력</p>
          {#if syncLogsLoading}
            <div class="text-neutral-600 text-sm">로딩 중...</div>
          {:else if syncLogs.length === 0}
            <div class="text-neutral-600 text-sm">동기화 이력이 없습니다.</div>
          {:else}
            <div class="space-y-2">
              {#each syncLogs as log (log.id)}
                <div class="flex items-start gap-3 text-xs">
                  <span class="text-neutral-500 shrink-0 w-36">{formatDateTime(log.created_at)}</span>
                  <span class="text-neutral-400">{log.actor_emp_no ?? log.actor}</span>
                  <span class="text-neutral-300 flex-1">{formatSyncDetail(log.detail)}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <!-- Staging editor (dev only) -->
      {#if showStagingSection}
        <div class="rounded-lg bg-[#141414] border border-neutral-800 p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-sm font-medium text-white">임시원장 편집</h3>
              <p class="text-xs text-neutral-500 mt-1">개발 환경 전용. ETL 없이 스테이징 데이터를 직접 관리합니다.</p>
            </div>
            <button
              onclick={() => { showNewStagingForm = !showNewStagingForm }}
              class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
            >
              + 행 추가
            </button>
          </div>

          {#if showNewStagingForm}
            <div class="flex flex-wrap items-center gap-2 mb-4 p-3 rounded-lg bg-[#1a1a1a] border border-neutral-700">
              <input type="text" bind:value={newStagingForm.emp_no} placeholder="행번 *"
                class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-24" />
              <input type="text" bind:value={newStagingForm.name} placeholder="이름 *"
                class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-28" />
              <select bind:value={newStagingForm.dept_code}
                class="rounded bg-neutral-900 border border-neutral-700 text-neutral-300 px-2 py-1 text-sm focus:outline-none w-32">
                <option value="">부서 선택 *</option>
                {#each allDepts as d (d.code)}
                  <option value={d.code}>{d.name}</option>
                {/each}
              </select>
              <input type="text" bind:value={newStagingForm.team_code} placeholder="팀코드"
                class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-24" />
              <input type="text" bind:value={newStagingForm.rank} placeholder="직급"
                class="rounded bg-neutral-900 border border-neutral-700 text-white placeholder:text-neutral-600 px-2 py-1 text-sm focus:outline-none w-24" />
              <button
                onclick={handleUpsertStaging}
                disabled={stagingFormLoading}
                class="rounded bg-white text-black text-xs font-medium px-3 py-1.5 hover:bg-neutral-200 transition-colors disabled:opacity-50"
              >
                {stagingFormLoading ? '저장 중...' : '저장'}
              </button>
              <button
                onclick={() => { showNewStagingForm = false }}
                class="text-xs text-neutral-500 hover:text-neutral-300 transition-colors px-2"
              >
                취소
              </button>
            </div>
          {/if}

          {#if stagingLoading}
            <SkeletonTable rows={3} cols={5} />
          {:else if stagingData.length === 0}
            <div class="py-6 text-center text-neutral-500 text-sm">스테이징 데이터가 없습니다.</div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr>
                    {#each ['행번', '이름', '부서', '팀', '직급', ''] as h (h)}
                      <th class="px-3 py-2 text-left border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider">{h}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each stagingData as row (row.emp_no)}
                    <tr class="border-b border-neutral-800/50">
                      <td class="px-3 py-2 text-neutral-300">{row.emp_no}</td>
                      <td class="px-3 py-2 text-neutral-300">{row.name}</td>
                      <td class="px-3 py-2 text-neutral-300">{row.dept_code}</td>
                      <td class="px-3 py-2 text-neutral-400">{row.team_code ?? '—'}</td>
                      <td class="px-3 py-2 text-neutral-400">{row.rank ?? '—'}</td>
                      <td class="px-3 py-2">
                        <button
                          onclick={() => handleDeleteStaging(row.emp_no)}
                          class="text-xs text-red-400 hover:text-red-300 transition-colors"
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- ── Tab: 감사 로그 ─────────────────────────────────────────────────────── -->
  {#if activeTab === 'audit'}
    <div class="space-y-4">
      <!-- Filters -->
      <div class="flex flex-wrap items-center gap-3">
        <select
          bind:value={auditFilters.action}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
        >
          <option value="">전체 액션</option>
          <option value="LOGIN">LOGIN</option>
          <option value="LOGIN_FAIL">LOGIN_FAIL</option>
          <option value="LOGOUT">LOGOUT</option>
          <option value="CREATE">CREATE</option>
          <option value="UPDATE">UPDATE</option>
          <option value="DELETE">DELETE</option>
          <option value="DOWNLOAD">DOWNLOAD</option>
          <option value="BATCH_RUN">BATCH_RUN</option>
        </select>

        <select
          bind:value={auditFilters.resource_type}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
        >
          <option value="">전체 리소스</option>
          <option value="Meeting">Meeting</option>
          <option value="MeetingRoom">MeetingRoom</option>
          <option value="Employee">Employee</option>
          <option value="Department">Department</option>
          <option value="Team">Team</option>
        </select>

        <input
          type="text"
          bind:value={auditFilters.actor_emp_no}
          placeholder="수행자 행번"
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600 w-36"
        />

        <input
          type="date"
          bind:value={auditFilters.date_from}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
        />
        <span class="text-neutral-500 text-sm">~</span>
        <input
          type="date"
          bind:value={auditFilters.date_to}
          class="rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
        />

        <button
          onclick={() => loadAuditLogs(1)}
          class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors"
        >
          검색
        </button>
      </div>

      <!-- Table -->
      <div class="rounded-lg bg-[#141414] border border-neutral-800">
        {#if auditLoading}
          <SkeletonTable rows={10} cols={6} />
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr>
                  {#each auditHeaders as h (h.key)}
                    <th class="px-4 py-3 text-left border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider">
                      {h.label}
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#if auditData.items.length === 0}
                  <tr>
                    <td colspan="6" class="px-4 py-8 text-center text-neutral-500">
                      조회 조건에 맞는 감사 로그가 없습니다.
                    </td>
                  </tr>
                {:else}
                  {#each auditData.items as log (log.id)}
                    <tr
                      onclick={() => openAuditDetail(log)}
                      class="border-b border-neutral-800/50 hover:bg-[#1f1f1f] transition-colors cursor-pointer"
                    >
                      <td class="px-4 py-3 text-neutral-400 text-xs whitespace-nowrap">{formatDateTime(log.created_at)}</td>
                      <td class="px-4 py-3">
                        <span class="rounded-md text-xs px-2 py-1 border
                          {log.action === 'LOGIN' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                           log.action === 'LOGIN_FAIL' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                           log.action === 'DELETE' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                           log.action === 'CREATE' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                           log.action === 'BATCH_RUN' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                           'bg-neutral-800 text-neutral-400 border-neutral-700'}">
                          {log.action}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-neutral-300">{log.resource_type ?? '—'}</td>
                      <td class="px-4 py-3 text-neutral-500 text-xs font-mono">{log.resource_id ? log.resource_id.slice(0, 8) + '…' : '—'}</td>
                      <td class="px-4 py-3 text-neutral-300">
                        {log.actor_name ? `${log.actor_name} (${log.actor_emp_no})` : (log.actor_emp_no ?? '—')}
                      </td>
                      <td class="px-4 py-3 text-neutral-500 text-xs">{log.ip_address ?? '—'}</td>
                    </tr>
                  {/each}
                {/if}
              </tbody>
            </table>
          </div>
          <div class="px-4">
            <Pagination
              page={auditData.page}
              pages={auditData.pages}
              total={auditData.total}
              onPageChange={(p) => loadAuditLogs(p)}
            />
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- Employee slide panel -->
<SlidePanel open={panelOpen} title={selectedEmp ? `${selectedEmp.name} (${selectedEmp.emp_no})` : ''} onClose={() => { panelOpen = false }}>
  {#if selectedEmp}
    <div class="space-y-6">
      <!-- Basic info -->
      <div>
        <p class="text-xs text-neutral-500 uppercase tracking-wider mb-3">기본 정보</p>
        <div class="space-y-3">
          <div>
            <label class="text-sm font-medium text-neutral-300 block mb-1">이름</label>
            <input
              type="text"
              bind:value={empEditForm.name}
              class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-neutral-300 block mb-1">부서코드</label>
            <select
              bind:value={empEditForm.dept_code}
              class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-neutral-300 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
            >
              {#each allDepts as d (d.code)}
                <option value={d.code}>{d.name} ({d.code})</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="text-sm font-medium text-neutral-300 block mb-1">직급</label>
            <input
              type="text"
              bind:value={empEditForm.rank}
              placeholder="직급 (선택)"
              class="w-full rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-3 py-2 text-sm focus:outline-none focus:border-neutral-600"
            />
          </div>
        </div>
        <button
          onclick={handleUpdateEmployee}
          disabled={updateLoading}
          class="mt-4 rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
        >
          {updateLoading ? '저장 중...' : '정보 저장'}
        </button>
      </div>

      <!-- Permissions -->
      <div>
        <p class="text-xs text-neutral-500 uppercase tracking-wider mb-3">권한 설정</p>
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm text-white">Admin 권한</span>
              <p class="text-xs text-neutral-500">모든 데이터 CRUD 및 권한 관리</p>
            </div>
            <button
              onclick={() => handlePermToggle('is_admin', !permForm.is_admin)}
              disabled={selectedEmp.status === 'RETIRED'}
              class="relative w-10 h-5 rounded-full transition-colors disabled:opacity-40 {permForm.is_admin ? 'bg-white' : 'bg-neutral-700'}"
              role="switch"
              aria-checked={permForm.is_admin}
            >
              <span
                class="absolute top-0.5 w-4 h-4 rounded-full bg-neutral-900 transition-transform {permForm.is_admin ? 'translate-x-5' : 'translate-x-0.5'}"
              ></span>
            </button>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm text-white">회의실 담당자</span>
              <p class="text-xs text-neutral-500">담당 부서 회의실·집기 관리</p>
            </div>
            <button
              onclick={() => handlePermToggle('is_room_manager', !permForm.is_room_manager)}
              disabled={selectedEmp.status === 'RETIRED'}
              class="relative w-10 h-5 rounded-full transition-colors disabled:opacity-40 {permForm.is_room_manager ? 'bg-white' : 'bg-neutral-700'}"
              role="switch"
              aria-checked={permForm.is_room_manager}
            >
              <span
                class="absolute top-0.5 w-4 h-4 rounded-full bg-neutral-900 transition-transform {permForm.is_room_manager ? 'translate-x-5' : 'translate-x-0.5'}"
              ></span>
            </button>
          </div>
        </div>
        {#if selectedEmp.status === 'RETIRED'}
          <p class="text-xs text-neutral-500 mt-2">퇴직 직원은 권한을 변경할 수 없습니다.</p>
        {/if}
      </div>

      <!-- Retire -->
      {#if selectedEmp.status === 'ACTIVE'}
        <div class="pt-4 border-t border-neutral-800">
          <button
            onclick={() => { retireModal = true }}
            class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors"
          >
            퇴직 처리
          </button>
        </div>
      {/if}
    </div>
  {/if}
</SlidePanel>

<!-- Retire confirm modal -->
<Modal
  title="퇴직 처리하시겠습니까?"
  open={retireModal}
  onClose={() => { retireModal = false }}
>
  <p class="text-sm text-neutral-300">
    퇴직 처리하면 해당 직원은 로그인할 수 없습니다.<br />
    <span class="text-neutral-500">이 작업은 ETL 재동기화로 복원될 수 있습니다.</span>
  </p>
  {#snippet footer()}
    <button
      onclick={() => { retireModal = false }}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      취소
    </button>
    <button
      onclick={handleRetire}
      disabled={retireLoading}
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors disabled:opacity-50"
    >
      {retireLoading ? '처리 중...' : '퇴직 처리'}
    </button>
  {/snippet}
</Modal>

<!-- Delete dept/team confirm modal -->
<Modal
  title={deleteModal.type === 'dept' ? '부서를 삭제하시겠습니까?' : '팀을 삭제하시겠습니까?'}
  open={deleteModal.open}
  onClose={() => { deleteModal = { open: false, type: '', item: null, loading: false } }}
>
  <p class="text-sm text-neutral-300">
    {deleteModal.item?.name}을(를) 삭제합니다.<br />
    <span class="text-neutral-500">소속 직원이 있으면 삭제할 수 없습니다.</span>
  </p>
  {#snippet footer()}
    <button
      onclick={() => { deleteModal = { open: false, type: '', item: null, loading: false } }}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      취소
    </button>
    <button
      onclick={() => deleteModal.type === 'dept' ? handleDeleteDept() : handleDeleteTeam()}
      disabled={deleteModal.loading}
      class="rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors disabled:opacity-50"
    >
      {deleteModal.loading ? '삭제 중...' : '삭제'}
    </button>
  {/snippet}
</Modal>

<!-- Permission change confirm modal -->
<Modal
  title="권한 변경"
  open={permConfirmModal.open}
  onClose={() => { permConfirmModal = { open: false, field: '', newValue: false } }}
>
  <p class="text-sm text-neutral-300">
    {permConfirmLabel()}
  </p>
  {#snippet footer()}
    <button
      onclick={() => { permConfirmModal = { open: false, field: '', newValue: false } }}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      취소
    </button>
    <button
      onclick={handleUpdatePermissions}
      disabled={updateLoading}
      class="rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors disabled:opacity-50"
    >
      {updateLoading ? '변경 중...' : '변경'}
    </button>
  {/snippet}
</Modal>

<!-- Audit log detail modal -->
<Modal
  title="감사 로그 상세"
  open={auditDetailOpen}
  onClose={() => { auditDetailOpen = false }}
>
  {#if auditDetailLog}
    <div class="space-y-4">
      <div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs">
        <span class="text-neutral-500">ID</span>
        <span class="text-neutral-300 font-mono">{auditDetailLog.id}</span>
        <span class="text-neutral-500">시각</span>
        <span class="text-neutral-300">{formatDateTime(auditDetailLog.created_at)}</span>
        <span class="text-neutral-500">액션</span>
        <span class="text-neutral-300">{auditDetailLog.action}</span>
        <span class="text-neutral-500">리소스</span>
        <span class="text-neutral-300">{auditDetailLog.resource_type ?? '—'}</span>
        <span class="text-neutral-500">리소스 ID</span>
        <span class="text-neutral-300 font-mono break-all">{auditDetailLog.resource_id ?? '—'}</span>
        <span class="text-neutral-500">수행자</span>
        <span class="text-neutral-300">
          {auditDetailLog.actor_name ? `${auditDetailLog.actor_name} (${auditDetailLog.actor_emp_no})` : (auditDetailLog.actor_emp_no ?? '—')}
        </span>
        <span class="text-neutral-500">IP</span>
        <span class="text-neutral-300">{auditDetailLog.ip_address ?? '—'}</span>
      </div>

      {#if auditDetailLog.detail !== null && auditDetailLog.detail !== undefined}
        <div>
          <p class="text-xs text-neutral-500 uppercase tracking-wider mb-2">상세 내용</p>
          <pre class="text-xs font-mono bg-neutral-900 border border-neutral-800 p-3 rounded-lg overflow-auto max-h-64 whitespace-pre-wrap text-neutral-300">{typeof auditDetailLog.detail === 'string' ? auditDetailLog.detail : JSON.stringify(auditDetailLog.detail, null, 2)}</pre>
        </div>
      {/if}
    </div>
  {/if}
  {#snippet footer()}
    <button
      onclick={() => { auditDetailOpen = false }}
      class="rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors"
    >
      닫기
    </button>
  {/snippet}
</Modal>
