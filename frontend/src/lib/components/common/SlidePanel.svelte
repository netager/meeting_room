<script>
  let { open = false, title = '', onClose, children } = $props()
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-40" onclick={() => onClose?.()}>
    <div class="absolute inset-0 bg-black/40"></div>
  </div>
  <div class="fixed right-0 top-0 bottom-0 w-[480px] bg-[#141414] border-l border-neutral-800 z-50 overflow-y-auto">
    <div class="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
      <h3 class="text-base font-semibold text-white">{title}</h3>
      <button
        onclick={() => onClose?.()}
        class="text-neutral-400 hover:text-white transition-colors p-1"
      >
        ✕
      </button>
    </div>
    <div class="p-6">
      {@render children?.()}
    </div>
  </div>
{/if}
