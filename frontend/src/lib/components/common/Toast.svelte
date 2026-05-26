<script>
  import { toasts, dismissToast } from '../../stores/toast.js'

  const typeStyles = {
    success: 'bg-green-500/10 border-green-500/20 text-green-400',
    error: 'bg-red-500/10 border-red-500/20 text-red-400',
    warning: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400',
    info: 'bg-neutral-800 border-neutral-700 text-neutral-300',
  }
</script>

<div class="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
  {#each $toasts as toast (toast.id)}
    <div
      class="flex items-start gap-3 rounded-lg border px-4 py-3 text-sm transition-opacity duration-200 {typeStyles[toast.type] || typeStyles.info}"
    >
      <span class="flex-1">{toast.message}</span>
      <button
        onclick={() => dismissToast(toast.id)}
        class="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="닫기"
      >
        ✕
      </button>
    </div>
  {/each}
</div>
