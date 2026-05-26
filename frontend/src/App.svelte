<script>
  import { onMount } from 'svelte'
  import { currentUser, initAuth, clearAuth } from './lib/stores/auth.js'
  import { currentRoute, routeParams, initRouter } from './router.js'
  import Toast from './lib/components/common/Toast.svelte'
  import AppShell from './lib/components/layout/AppShell.svelte'
  import Login from './pages/Login.svelte'
  import PasswordChange from './pages/PasswordChange.svelte'
  import Dashboard from './pages/Dashboard.svelte'
  import Admin from './pages/Admin.svelte'
  import MeetingRooms from './pages/MeetingRooms.svelte'
  import MeetingList from './pages/MeetingList.svelte'
  import MeetingForm from './pages/MeetingForm.svelte'
  import MeetingDetail from './pages/MeetingDetail.svelte'

  onMount(async () => {
    window.addEventListener('auth:session-expired', () => {
      clearAuth()
    })

    await initAuth()
    initRouter()
  })
</script>

<Toast />

{#if !$currentUser}
  <Login />
{:else if $currentRoute === '/password-change'}
  <PasswordChange />
{:else}
  <AppShell>
    {#if $currentRoute === '/admin'}
      <Admin />
    {:else if $currentRoute === '/rooms' || $currentRoute === '/room-management'}
      <MeetingRooms />
    {:else if $currentRoute === '/meetings'}
      <MeetingList />
    {:else if $currentRoute === '/meetings/new'}
      <MeetingForm />
    {:else if $currentRoute === '/meetings/:id/edit'}
      <MeetingForm meetingId={$routeParams.id} />
    {:else if $currentRoute === '/meetings/:id'}
      <MeetingDetail meetingId={$routeParams.id} />
    {:else}
      <Dashboard />
    {/if}
  </AppShell>
{/if}
