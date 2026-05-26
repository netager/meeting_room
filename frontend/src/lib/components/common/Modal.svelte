<script>
  let { title, open = false, onClose, children, footer } = $props()

  function handleOverlayClick() {
    onClose?.()
  }

  function handlePanelClick(e) {
    e.stopPropagation()
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={handleOverlayClick}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div
      class="rounded-lg bg-[#141414] border border-neutral-800 p-6 max-w-lg w-full mx-4"
      onclick={handlePanelClick}
    >
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-white">{title}</h2>
        <button
          onclick={() => onClose?.()}
          class="text-neutral-400 hover:text-white transition-colors p-1"
          autofocus
        >
          ✕
        </button>
      </div>
      <div>
        {@render children?.()}
      </div>
      {#if footer}
        <div class="flex justify-end gap-2 mt-6">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
