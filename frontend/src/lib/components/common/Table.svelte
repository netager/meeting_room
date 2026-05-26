<script>
  let { headers = [], rows = [], onRowClick, cell, empty } = $props()
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr>
        {#each headers as col (col.key)}
          <th class="px-4 py-3 text-left border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider font-medium whitespace-nowrap">
            {col.label}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if rows.length === 0}
        {#if empty}
          {@render empty()}
        {:else}
          <tr>
            <td colspan={headers.length} class="px-4 py-8 text-center text-neutral-500">
              데이터가 없습니다.
            </td>
          </tr>
        {/if}
      {:else}
        {#each rows as row, i (i)}
          <tr
            class="border-b border-neutral-800/50 transition-colors {onRowClick ? 'cursor-pointer hover:bg-[#1f1f1f]' : ''}"
            onclick={() => onRowClick?.(row, i)}
          >
            {#each headers as col (col.key)}
              <td class="px-4 py-3 text-neutral-300">
                {#if cell}
                  {@render cell(row, col)}
                {:else}
                  {row[col.key] ?? '—'}
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
