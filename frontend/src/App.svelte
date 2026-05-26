<script>
  import { onMount } from 'svelte'
  import { currentUser, initAuth, clearAuth } from './lib/stores/auth.js'
  import { currentRoute, initRouter } from './router.js'
  import Toast from './lib/components/common/Toast.svelte'
  import AppShell from './lib/components/layout/AppShell.svelte'
  import Login from './pages/Login.svelte'
  import PasswordChange from './pages/PasswordChange.svelte'
  import Dashboard from './pages/Dashboard.svelte'

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
    <!-- Route-based page rendering — additional routes added in later phases -->
    <Dashboard />
  </AppShell>
{/if}
