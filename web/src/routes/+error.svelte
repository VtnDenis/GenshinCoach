<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';

	const status = $derived(page.status);
	const title = $derived(status === 404 ? 'Page introuvable.' : 'Ça a coincé.');
	const detail = $derived(
		status === 404
			? 'Cette page n’existe pas ou plus. Ta vitrine et tes conversations sont intactes.'
			: (page.error?.message ?? 'Une erreur inattendue est survenue.')
	);
</script>

<svelte:head><title>Oups · GenshinCoach</title></svelte:head>

<main class="flex min-h-[100dvh] items-center justify-center px-4 py-10 text-ink">
	<div class="w-full max-w-md rounded-window bg-surface p-6 text-center sm:p-8">
		<p class="font-mono text-[11px] tracking-[0.16em] text-sport uppercase" aria-hidden="true">
			Erreur {status}
		</p>
		<h1 class="mt-1 text-xl font-semibold tracking-tight">{title}</h1>
		<p class="mt-2 text-sm leading-relaxed text-ink-2">{detail}</p>
		<div class="mt-5 flex flex-col gap-1.5">
			<button
				type="button"
				onclick={() => goto('/')}
				class="rc-press min-h-11 w-full rounded-control bg-sport px-4 text-sm font-semibold text-[#2a2113]"
				>Retour au coach</button
			>
			<div class="flex gap-1.5">
				<button
					type="button"
					onclick={() => goto('/vitrine')}
					class="min-h-11 flex-1 rounded-control bg-field px-3 text-[13px] text-ink"
					>Vitrine</button
				>
				<button
					type="button"
					onclick={() => goto('/news')}
					class="min-h-11 flex-1 rounded-control bg-field px-3 text-[13px] text-ink"
					>News</button
				>
			</div>
		</div>
	</div>
</main>
