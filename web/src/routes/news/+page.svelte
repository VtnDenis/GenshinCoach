<script lang="ts">
	import { goto } from '$app/navigation';
	import { fetchNews, type NewsItem } from '$lib/api';
	import Wordmark from '$lib/components/Wordmark.svelte';
	import LoadingState from '$lib/components/LoadingState.svelte';
	import { rise } from '$lib/motion';

	let q = $state('patch notes version actuelle bannières');
	let answer = $state('');
	let results: NewsItem[] = $state([]);
	let loading = $state(false);
	let error = $state('');

	async function search() {
		const needle = q.trim();
		if (!needle || loading) return;
		loading = true;
		error = '';
		try {
			const r = await fetchNews(needle, 6);
			answer = r.answer;
			results = r.results;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>News · GenshinCoach</title></svelte:head>

<div class="flex min-h-[100dvh] flex-col bg-page text-ink">
	<header class="rc-sportline flex shrink-0 items-center gap-2 border-b border-line bg-surface-warm px-3 py-2">
		<button
			type="button"
			onclick={() => goto('/')}
			class="rc-press min-h-11 rounded-control px-3 text-[13px] font-medium text-ink-2 hover:bg-hover hover:text-ink"
			aria-label="Retour au chat">← Chat</button
		>
		<Wordmark class="text-[18px]" />
		<h1 class="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight">News patch</h1>
	</header>

	<main class="mx-auto w-full max-w-3xl flex-1 px-4 py-4 sm:px-6 sm:py-6">
		<form
			onsubmit={(e) => {
				e.preventDefault();
				search();
			}}
			class="flex gap-1.5"
		>
			<input
				bind:value={q}
				aria-label="Recherche news"
				placeholder="Ex : bannières en cours, patch notes…"
				class="min-w-0 flex-1 rounded-control border border-line bg-surface px-3 py-2.5 text-[15px] text-ink shadow-hairline outline-none placeholder:text-ink-3 focus:border-sport/60"
			/>
			<button
				type="submit"
				disabled={loading}
				class="rc-press rc-btn-primary min-h-11 rounded-full px-5 text-[14px] font-semibold disabled:opacity-40"
			>
				{loading ? '…' : 'Chercher'}
			</button>
		</form>

		{#if loading}
			<div class="mt-4"><LoadingState label="News" /></div>
		{:else if error}
			<p class="mt-4 text-sm text-red" role="alert">Erreur : {error}</p>
		{:else}
			{#if answer}
				<p use:rise class="mt-4 rounded-card border border-line bg-surface px-4 py-3 text-sm leading-relaxed shadow-card">
					<strong class="font-semibold">Résumé :</strong> {answer}
				</p>
			{/if}
			<ul class="mt-3 flex flex-col gap-2">
				{#each results as r (r.url)}
					<li use:rise class="rounded-card border border-line bg-surface px-4 py-3 shadow-card">
						<a href={r.url} target="_blank" rel="noopener" class="text-[15px] font-medium text-accent-ink hover:underline">
							{r.title}
						</a>
						{#if r.snippet}
							<p class="mt-1 text-[13px] leading-snug text-ink-2">{r.snippet}</p>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</main>
</div>
