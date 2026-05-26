<script>
  import { currentUser } from '../../stores/auth.js'
  import { currentRoute, navigateTo } from '../../../router.js'
  import { logout } from '../../api/auth.js'
  import { clearAuth } from '../../stores/auth.js'
  import { showToast } from '../../stores/toast.js'

  let { children } = $props()

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // ignore errors — still clear local state
    }
    clearAuth()
    navigateTo('#/login')
    showToast('로그아웃 되었습니다.', 'info')
  }

  function isActive(path) {
    return $currentRoute === path
  }

  const navItemClass = (path) =>
    `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer ` +
    (isActive(path)
      ? 'bg-[#1f1f1f] text-white'
      : 'text-neutral-400 hover:bg-[#1f1f1f] hover:text-white')
</script>

<div class="flex h-screen bg-[#0a0a0a] overflow-hidden">
  <!-- Sidebar -->
  <aside class="w-56 shrink-0 flex flex-col bg-[#0a0a0a] border-r border-neutral-800">
    <!-- Logo -->
    <div class="px-4 py-5 border-b border-neutral-800">
      <h1 class="text-sm font-semibold text-white leading-tight">회의 및 회의실 관리</h1>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
      <button class={navItemClass('/')} onclick={() => navigateTo('#/')}>
        내 회의
      </button>
      <button class={navItemClass('/meetings')} onclick={() => navigateTo('#/meetings')}>
        전체 회의
      </button>
      <button class={navItemClass('/rooms')} onclick={() => navigateTo('#/rooms')}>
        회의실 현황
      </button>

      {#if $currentUser?.is_room_manager || $currentUser?.is_admin}
        <div class="pt-4">
          <p class="px-3 pb-1 text-xs text-neutral-500 uppercase tracking-wider">회의실 담당</p>
          <button class={navItemClass('/room-management')} onclick={() => navigateTo('#/room-management')}>
            회의실 관리
          </button>
        </div>
      {/if}

      {#if $currentUser?.is_admin}
        <div class="pt-4">
          <p class="px-3 pb-1 text-xs text-neutral-500 uppercase tracking-wider">관리자</p>
          <button class={navItemClass('/admin')} onclick={() => navigateTo('#/admin')}>
            관리자 메뉴
          </button>
        </div>
      {/if}
    </nav>

    <!-- User info & logout -->
    <div class="px-2 py-4 border-t border-neutral-800">
      <button
        class="w-full px-3 py-2 rounded-lg text-left hover:bg-[#1f1f1f] transition-colors"
        onclick={() => navigateTo('#/password-change')}
      >
        <p class="text-sm text-white truncate">{$currentUser?.name || $currentUser?.emp_no}</p>
        <p class="text-xs text-neutral-500 truncate">{$currentUser?.emp_no}</p>
      </button>
      <button
        class="w-full mt-1 px-3 py-2 rounded-lg text-sm text-neutral-400 hover:bg-[#1f1f1f] hover:text-white transition-colors text-left"
        onclick={handleLogout}
      >
        로그아웃
      </button>
    </div>
  </aside>

  <!-- Main content -->
  <main class="flex-1 overflow-y-auto">
    {@render children()}
  </main>
</div>
