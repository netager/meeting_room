<script>
  let { page = 1, pages = 1, total = 0, onPageChange } = $props()

  function computePageNumbers(currentPage, totalPages) {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }
    const nums = [1]
    if (currentPage > 4) nums.push('...')
    const start = Math.max(2, currentPage - 2)
    const end = Math.min(totalPages - 1, currentPage + 2)
    for (let i = start; i <= end; i++) nums.push(i)
    if (currentPage < totalPages - 3) nums.push('...')
    nums.push(totalPages)
    return nums
  }

  let pageNumbers = $derived(computePageNumbers(page, pages))

  function goTo(p) {
    if (p >= 1 && p <= pages && p !== page) {
      onPageChange?.(p)
    }
  }

  const btnBase = 'min-w-[32px] h-8 px-2 rounded text-xs transition-colors'
  const btnActive = 'bg-white text-black font-medium'
  const btnInactive = 'text-neutral-400 hover:bg-[#1f1f1f] hover:text-white'
  const btnDisabled = 'text-neutral-600 cursor-not-allowed'
</script>

<div class="flex items-center justify-between pt-4">
  <p class="text-xs text-neutral-500">총 {total}건</p>
  {#if pages > 1}
    <div class="flex items-center gap-1">
      <button
        onclick={() => goTo(page - 1)}
        disabled={page <= 1}
        class="{btnBase} {page <= 1 ? btnDisabled : btnInactive}"
      >
        이전
      </button>
      {#each pageNumbers as p (p)}
        {#if p === '...'}
          <span class="px-1 text-xs text-neutral-600">…</span>
        {:else}
          <button
            onclick={() => goTo(p)}
            class="{btnBase} {p === page ? btnActive : btnInactive}"
          >
            {p}
          </button>
        {/if}
      {/each}
      <button
        onclick={() => goTo(page + 1)}
        disabled={page >= pages}
        class="{btnBase} {page >= pages ? btnDisabled : btnInactive}"
      >
        다음
      </button>
    </div>
  {/if}
</div>
