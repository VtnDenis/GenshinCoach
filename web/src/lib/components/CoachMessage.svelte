<script lang="ts">
	import { renderMd, type Step } from '$lib/api';
	import 'katex/dist/katex.min.css';
	import '$lib/md.css';
	import Thinking from './Thinking.svelte';

	let { text, model = null, steps = [], onRetry = null, retrying = false }: { text: string; model?: string | null; steps?: Step[]; onRetry?: (() => void) | null; retrying?: boolean } = $props();
	let copied = $state(false);

	let stepRows = $derived(
		(steps ?? []).map((s) => ({
			primary: s.error ? `${s.tool} · erreur` : s.tool,
			secondary: s.ms != null ? `${s.ms}ms` : undefined,
			detail: s.result || undefined
		}))
	);

	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			/* clipboard unavailable, still show feedback */
		}
		copied = true;
		window.setTimeout(() => (copied = false), 1400);
	}
</script>

<div class="w-full">
	{#if stepRows.length > 0}
		<div class="mb-2 rounded-card border border-line bg-surface px-4 py-2">
			<Thinking
				rows={stepRows}
				working={false}
				doneLabel={`Task trace · ${stepRows.length} outil${stepRows.length > 1 ? 's' : ''}`}
				startOpen={false}
			/>
		</div>
	{/if}
	<div
		class="md space-y-2 rounded-card border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink [&_p]:my-1 [&_strong]:font-semibold"
	>
		{@html renderMd(text)}
	</div>
	<div class="mt-1.5 flex items-center gap-1">
		<button
			type="button"
			onclick={copy}
			class="flex min-h-11 items-center gap-1.5 rounded-md px-1.5 text-xs text-ink-3 transition-colors hover:bg-hover hover:text-ink-2 sm:min-h-7"
			aria-label="Copier la réponse"
		>
			<svg
				width="14"
				height="14"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.8"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				{#if copied}
					<path d="M20 6L9 17l-5-5" />
				{:else}
					<rect x="9" y="9" width="12" height="12" rx="2.5" />
					<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
				{/if}
			</svg>
			{copied ? 'Copié' : 'Copier'}
		</button>
		{#if onRetry}
			<button
				type="button"
				onclick={onRetry}
				disabled={retrying}
				class="flex min-h-11 items-center gap-1.5 rounded-md px-1.5 text-xs text-ink-3 transition-colors hover:bg-hover hover:text-ink-2 disabled:opacity-50 sm:min-h-7"
				aria-label="Réessayer cette réponse"
			>
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="M3 12a9 9 0 1 0 3-6.7" />
					<path d="M3 4v5h5" />
				</svg>
				{retrying ? 'Retry…' : 'Réessayer'}
			</button>
		{/if}
		{#if model}
			<span class="ml-auto text-[11px] text-ink-3">via {model}</span>
		{/if}
	</div>
</div>
