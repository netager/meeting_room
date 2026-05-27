<script>
  import { onMount, onDestroy } from 'svelte'
  import { navigateTo } from '../../../router.js'
  import {
    notifications,
    unreadCount,
    fetchNotifications,
    resetUnreadCount,
  } from '../../stores/notifications.js'

  let isOpen = $state(false)
  let dropdownEl = $state(null)

  const EVENT_TYPE_LABELS = {
    CREATED: '회의 신청',
    UPDATED: '회의 수정',
    CANCELLED: '회의 취소',
    COMPLETED: '회의 완료',
    ATTENDEE_ADDED: '참석자 추가',
    ATTENDEE_REMOVED: '참석자 제거',
    DIRECT: '직접 메시지',
  }

  function getEventTypeLabel(eventType) {
    return EVENT_TYPE_LABELS[eventType] || eventType
  }

  function formatRelativeTime(dateStr) {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const mins = Math.floor(diffMs / 60000)
    const hours = Math.floor(diffMs / 3600000)
    const days = Math.floor(diffMs / 86400000)

    if (diffMs < 60000) return '방금 전'
    if (mins < 60) return `${mins}분 전`
    if (hours < 24) return `${hours}시간 전`
    return `${days}일 전`
  }

  function toggleDropdown() {
    if (isOpen) {
      isOpen = false
    } else {
      isOpen = true
      resetUnreadCount()
      fetchNotifications()
    }
  }

  function handleClickOutside(e) {
    if (dropdownEl && !dropdownEl.contains(e.target)) {
      isOpen = false
    }
  }

  function goToNotifications() {
    isOpen = false
    navigateTo('#/notifications')
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside)
  })

  onDestroy(() => {
    document.removeEventListener('click', handleClickOutside)
  })
</script>

<div class="relative" bind:this={dropdownEl}>
  <!-- Bell button -->
  <button
    onclick={toggleDropdown}
    class="relative p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-[#1f1f1f] transition-colors"
    aria-label="알림"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="w-5 h-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="1.5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
      />
    </svg>
    {#if $unreadCount > 0}
      <span
        class="absolute top-1 right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium flex items-center justify-center leading-none"
      >
        {$unreadCount > 99 ? '99+' : $unreadCount}
      </span>
    {/if}
  </button>

  <!-- Dropdown panel -->
  {#if isOpen}
    <div
      class="absolute right-0 mt-2 w-80 rounded-lg bg-[#141414] border border-neutral-800 shadow-lg z-50"
    >
      <!-- Header -->
      <div class="px-4 py-3 border-b border-neutral-800">
        <h3 class="text-sm font-medium text-white">알림</h3>
      </div>

      {#if $notifications.length === 0}
        <div class="px-4 py-8 text-center text-sm text-neutral-500">알림이 없습니다.</div>
      {:else}
        <!-- Notification list (max 5) -->
        <div class="max-h-[400px] overflow-y-auto">
          {#each $notifications.slice(0, 5) as notification (notification.id)}
            <div
              class="px-4 py-3 border-b border-neutral-800/50 hover:bg-[#1f1f1f] transition-colors
                {notification.status === 'FAILED' ? 'border-l-2 border-l-red-500/70' : ''}
                {notification.status === 'PENDING' || notification.status === 'SENDING'
                ? 'opacity-60'
                : ''}"
            >
              <div class="flex items-start justify-between gap-2 mb-1.5">
                <span
                  class="text-xs px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 border border-neutral-700 shrink-0"
                >
                  {getEventTypeLabel(notification.event_type)}
                </span>
                <span class="text-xs text-neutral-500 shrink-0">
                  {formatRelativeTime(notification.created_at)}
                </span>
              </div>
              <p class="text-sm text-neutral-300 leading-relaxed line-clamp-2">
                {notification.message}
              </p>
            </div>
          {/each}
        </div>

        <!-- More link -->
        <button
          onclick={goToNotifications}
          class="w-full px-4 py-3 text-sm text-neutral-400 hover:text-white hover:bg-[#1f1f1f] transition-colors text-center rounded-b-lg"
        >
          더 보기 →
        </button>
      {/if}
    </div>
  {/if}
</div>
