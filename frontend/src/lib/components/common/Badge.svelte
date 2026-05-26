<script>
  let { text, variant = 'neutral' } = $props()

  const variantClasses = {
    success: 'bg-green-500/10 text-green-400 border-green-500/20',
    error: 'bg-red-500/10 text-red-400 border-red-500/20',
    warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    neutral: 'bg-neutral-800 text-neutral-400 border-neutral-700',
  }
</script>

<span class="rounded-md text-xs px-2 py-1 border {variantClasses[variant] ?? variantClasses.neutral}">
  {text}
</span>
