<script lang="ts">
	let {
		text,
		secs = null,
		streaming = false
	}: {
		text: string;
		secs?: number | null;
		streaming?: boolean;
	} = $props();

	let label = $derived(
		streaming ? 'Réfléchit…' : secs != null ? `Réflexion (${secs}s)` : 'Réflexion'
	);
</script>

<details open={streaming} class="mb-2 rounded-card border border-line bg-surface px-4 py-2">
	<summary
		class="flex cursor-pointer list-none items-center gap-2 text-[13px] text-ink-3 select-none hover:text-ink-2 [&::-webkit-details-marker]:hidden"
	>
		{#if streaming}
			<span class="relative flex size-2 shrink-0" aria-hidden="true">
				<span
					class="absolute inline-flex h-full w-full animate-ping rounded-full bg-sport opacity-60"
				></span>
				<span class="relative inline-flex size-2 rounded-full bg-sport"></span>
			</span>
		{:else}
			<svg
				width="12"
				height="12"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2.2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
				class="shrink-0"
			>
				<path d="M6 9l6 6 6-6" />
			</svg>
		{/if}
		<span class="font-medium">{label}</span>
	</summary>
	<p class="mt-1.5 max-h-48 overflow-y-auto text-[13px] leading-relaxed whitespace-pre-wrap text-ink-2">
		{text}
	</p>
</details>
