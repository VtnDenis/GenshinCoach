<script lang="ts">
	interface Row {
		primary: string;
		secondary?: string;
		detail?: string;
	}

	let {
		rows = [],
		working = true,
		activeLabel = 'Analyse de tes runs…',
		doneLabel = 'Analyse terminée',
		startOpen = true
	}: {
		rows?: Row[];
		working?: boolean;
		activeLabel?: string;
		doneLabel?: string;
		startOpen?: boolean;
	} = $props();

	let expanded = $state(startOpen);
</script>

<div class="w-full">
	<button
		type="button"
		class="rc-press -mx-1.5 flex w-fit min-h-11 items-center gap-2 rounded-full px-2.5 py-1 hover:bg-hover"
		aria-expanded={expanded}
		onclick={() => (expanded = !expanded)}
	>
		<span
			class="flex size-5 items-center justify-center rounded-full bg-field shadow-hairline"
			aria-hidden="true"
		>
			<svg width="12" height="12" viewBox="0 0 24 24" fill="var(--ink-2)" aria-hidden="true">
				<path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
			</svg>
		</span>
		{#if working}
			<span class="shimmer-label text-[13px] font-medium whitespace-nowrap">{activeLabel}</span>
			<span class="size-1.5 rounded-full bg-accent-ink" style="animation:pulse-soft 1.2s ease-in-out infinite" aria-hidden="true"></span>
		{:else}
			<span class="text-[13px] font-medium whitespace-nowrap text-ink-2">{doneLabel}</span>
			{#if rows.length}<span class="rounded-full bg-field px-1.5 py-0.5 font-mono text-[10px] text-ink-3 tabular-nums">{rows.length}</span>{/if}
		{/if}
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="var(--ink-3)"
			stroke-width="2.2"
			stroke-linecap="round"
			stroke-linejoin="round"
			class="transition-transform duration-300 {expanded ? 'rotate-180' : ''}"
			aria-hidden="true"
		>
			<path d="M6 9l6 6 6-6" />
		</svg>
	</button>

	{#if expanded}
		<div class="relative mt-1 ml-[5px] pl-4" style="animation:fade-up 320ms cubic-bezier(0.23,1,0.32,1) both">
			<span aria-hidden="true" class="absolute top-0 left-[3px] h-full w-px bg-line"></span>
			<ul class="flex flex-col gap-1 py-1">
				{#each rows as r, i}
					<li
						class="flex flex-col gap-0.5 text-xs"
						style="animation:fade-up 320ms cubic-bezier(0.23,1,0.32,1) {i * 90}ms both"
					>
					<span class="flex items-center gap-2">
						<span class="flex size-3 shrink-0 items-center justify-center" aria-hidden="true">
							{#if working && i === rows.length - 1}
								<span
									class="block size-3 rounded-full border-[1.5px] border-line-strong border-t-ink-2"
									style="animation:spin 700ms linear infinite"
								></span>
							{:else}
								<svg
									width="13"
									height="13"
									viewBox="0 0 24 24"
									fill="none"
									stroke="var(--ink-3)"
									stroke-width="3"
									stroke-linecap="round"
									stroke-linejoin="round"
								>
									<path d="M20 6L9 17l-5-5" />
								</svg>
							{/if}
						</span>
						<span class="text-ink-2">{r.primary}</span>
						{#if r.secondary}
							<span class="ml-auto pl-2 font-mono text-[11px] whitespace-nowrap text-ink-3">{r.secondary}</span>
						{/if}
					</span>
					{#if r.detail}
						<span class="ml-5 line-clamp-2 text-[11px] leading-snug text-ink-3">{r.detail}</span>
					{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>
