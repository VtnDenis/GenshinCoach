<script lang="ts">
	let {
		draft = $bindable(''),
		busy = false,
		selectedLabel = null,
		onSend,
		onClearSelected
	}: {
		draft: string;
		busy?: boolean;
		selectedLabel?: string | null;
		onSend: () => void;
		onClearSelected: () => void;
	} = $props();

	let ta: HTMLTextAreaElement | null = $state(null);

	function autoresize() {
		if (!ta) return;
		ta.style.height = 'auto';
		ta.style.height = Math.min(160, ta.scrollHeight) + 'px';
	}

	$effect(() => {
		draft;
		autoresize();
	});

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			onSend();
		}
	}
</script>

<div
	class="rounded-[26px] border border-line bg-surface p-2 shadow-overlay transition-shadow focus-within:border-sport/60 focus-within:shadow-[0_16px_48px_rgb(138_100_32/0.25)]"
>
	{#if selectedLabel}
		<div class="flex flex-wrap gap-1.5 px-1 pt-1 pb-2">
			<span
				class="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-field py-1 pr-1.5 pl-2.5 text-xs text-ink-2 shadow-hairline sm:min-h-7"
			>
				<span class="max-w-55 truncate">◉ {selectedLabel}</span>
				<button
					type="button"
					onclick={onClearSelected}
					class="rc-press flex size-6 items-center justify-center rounded-full text-ink-3 hover:bg-hover hover:text-ink"
					aria-label="Retirer le run ciblé">×</button
				>
			</span>
		</div>
	{/if}
	<div class="flex items-end gap-1.5">
		<textarea
			bind:this={ta}
			rows="2"
			bind:value={draft}
			disabled={busy}
			placeholder="Que veux-tu optimiser : builds, teams, progression…"
			aria-label="Message"
			onkeydown={keydown}
			oninput={autoresize}
			class="max-h-40 min-h-11 w-full min-w-0 flex-1 resize-none bg-transparent px-2.5 py-2.5 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-3 disabled:opacity-50"
		></textarea>
		<span
			class="mb-2 hidden shrink-0 items-center rounded-full bg-field px-2.5 py-1 font-mono text-[10.5px] whitespace-nowrap text-ink-3"
			title="Modèle côté serveur (OMNIROUTE_MODEL)">go</span
		>
		<button
			type="button"
			onclick={onSend}
			disabled={busy || !draft.trim()}
			class="rc-press rc-btn-primary flex size-11 shrink-0 items-center justify-center rounded-full text-white disabled:opacity-30"
			aria-label="Envoyer"
		>
			<svg
				width="17"
				height="17"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2.2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M12 19V5M5 12l7-7 7 7" />
			</svg>
		</button>
	</div>
</div>
