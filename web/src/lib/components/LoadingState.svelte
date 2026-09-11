<script lang="ts">
	import { onMount } from 'svelte';

	let { label = 'Analyse' }: { label?: string } = $props();
	let ds = $state(0);

	// ponytail: single Drive pattern, skip Dots/Orbit variants
	const delays = [90, 180, 270, 0, 90, 180, 90, 180, 270];

	onMount(() => {
		const t = window.setInterval(() => (ds += 1), 100);
		return () => window.clearInterval(t);
	});

	let elapsed = $derived.by(() => {
		const s = ds / 10;
		return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${(s % 60).toFixed(1)}s`;
	});
</script>

<div class="flex w-fit items-center gap-2.5" role="status" aria-label={`${label}, ${elapsed}`}>
	<span class="grid shrink-0 grid-cols-[repeat(3,4px)] gap-[1.5px]" aria-hidden="true">
		{#each delays as d}
			<span
				class="size-[4px] rounded-[1px] bg-accent-ink"
				style="opacity:0.15;animation:pixel-on 650ms ease-in-out {d}ms infinite"
			></span>
		{/each}
	</span>
	<span class="shimmer-label text-[13px] font-medium">{label}</span>
	<span class="rounded-full bg-field px-1.5 py-0.5 font-mono text-[11px] text-ink-3 tabular-nums">{elapsed}</span>
</div>
