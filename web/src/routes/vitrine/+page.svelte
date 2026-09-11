<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fetchShowcase, getUid, setUid, EL_COLOR, rarColor, type Showcase } from '$lib/api';
	import Wordmark from '$lib/components/Wordmark.svelte';
	import LoadingState from '$lib/components/LoadingState.svelte';
	import { rise } from '$lib/motion';

	let showcase = $state<Showcase | null>(null);
	let loading = $state(true);
	let error = $state('');
	let uid = $state('702342940');

	onMount(async () => {
		try {
			uid = getUid();
		} catch {
			/* private mode */
		}
		await load();
	});

	async function load() {
		loading = true;
		error = '';
		try {
			showcase = await fetchShowcase(uid);
			setUid(uid);
		} catch (e) {
			error = (e as Error).message;
			showcase = null;
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Vitrine · GenshinCoach</title></svelte:head>

<div class="flex min-h-[100dvh] flex-col bg-page text-ink">
	<header class="rc-sportline flex shrink-0 items-center gap-2 border-b border-line bg-surface-warm px-3 py-2">
		<button
			type="button"
			onclick={() => goto('/')}
			class="rc-press min-h-11 rounded-control px-3 text-[13px] font-medium text-ink-2 hover:bg-hover hover:text-ink"
			aria-label="Retour au chat">← Chat</button
		>
		<Wordmark class="text-[18px]" />
		<h1 class="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight">Vitrine</h1>
		<input
			bind:value={uid}
			inputmode="numeric"
			aria-label="UID"
			class="w-28 rounded-control bg-inset px-2.5 py-2 font-mono text-[13px] text-ink shadow-hairline outline-none"
		/>
		<button
			type="button"
			onclick={load}
			disabled={loading}
			class="rc-press rc-btn-primary min-h-11 rounded-full px-4 text-[13px] font-semibold disabled:opacity-40"
		>
			{loading ? '…' : 'Actualiser'}
		</button>
	</header>

	<main class="mx-auto w-full max-w-3xl flex-1 px-4 py-4 sm:px-6 sm:py-6">
		{#if loading}
			<LoadingState label="Vitrine Enka" />
		{:else if error || !showcase}
			<p class="text-sm text-red" role="alert">Erreur : {error || 'inconnue'}</p>
		{:else}
			<div use:rise>
				<p class="font-mono text-[11px] tracking-[0.16em] text-sport uppercase">
					{showcase.player.nickname} — AR{showcase.player.level} WL{showcase.player.worldLevel}
				</p>
				{#if !showcase.detailed}
					<p class="mt-2 rounded-card border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink-2">
						Vitrine détaillée masquée : en jeu, menu Paimon → carte profil → crayon →
						onglet Vitrine → cocher « Afficher les détails des personnages ».
					</p>
				{/if}
			</div>
			<ul class="mt-4 flex flex-col gap-2">
				{#each showcase.characters.length ? showcase.characters : showcase.preview as c (c.id)}
					<li use:rise class="rounded-card border border-line bg-surface px-4 py-3 shadow-card">
						<p class="text-[15px] font-semibold tracking-tight">
							<span style="color:{rarColor(c.rarity)}">★{c.rarity}</span>
							{c.name}
							<span class="ml-1 font-mono text-xs font-normal text-ink-3">niv. {c.level}</span>
							<span
								class="ml-1 rounded-full px-1.5 py-0.5 font-mono text-[10px] font-bold"
								style="color:{EL_COLOR[c.element] ?? 'var(--ink-3)'};background:color-mix(in srgb, {EL_COLOR[c.element] ?? 'var(--ink-3)'} 14%, transparent)"
							>{c.element}</span>
						</p>
						{#if c.crit_rate}
							<p class="mt-0.5 font-mono text-xs text-ink-2 tabular-nums">
								crit {c.crit_rate.toFixed(0)}/{(c.crit_dmg ?? 0).toFixed(0)}
							</p>
						{/if}
						{#if c.findings?.length}
							<ul class="mt-1.5 flex flex-col gap-1">
								{#each c.findings as f}
									<li class="text-[13px] leading-snug text-ink-2">• {f}</li>
								{/each}
							</ul>
						{/if}
					</li>
				{/each}
			</ul>
			{#if showcase.priorities.length}
				<h2 class="mt-6 text-lg font-semibold tracking-tight">Priorités</h2>
				<ul class="mt-2 flex flex-col gap-2">
					{#each showcase.priorities as p}
						<li class="rounded-card border border-line bg-surface px-4 py-2.5 text-sm leading-relaxed shadow-card">{p}</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</main>
</div>
