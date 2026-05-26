<script>
  let { rows = 5, cols = 4 } = $props()
  let rowRange = $derived(Array.from({ length: rows }, (__, i) => i))
  let colRange = $derived(Array.from({ length: cols }, (__, i) => i))
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr>
        {#each colRange as i (i)}
          <th class="px-4 py-3 border-b border-neutral-800">
            <div class="h-3 w-20 rounded bg-neutral-800 animate-pulse"></div>
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rowRange as i (i)}
        <tr class="border-b border-neutral-800/50">
          {#each colRange as j (j)}
            <td class="px-4 py-3">
              <div class="h-4 rounded bg-neutral-800 animate-pulse w-3/4"></div>
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>
