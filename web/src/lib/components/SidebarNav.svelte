<script lang="ts">
	import { goto } from '$app/navigation';
	import { EL_COLOR, rarColor, type Session, type ShowcaseChar } from '$lib/api';

	let {
		sessions,
		sid = null,
		loadingSessions = false,
		openingId = null,
		deletingId = null,
		chars,
		charsLoading = false,
		uid,
		onNew,
		onOpen,
		onDelete,
		onUidChange
	}: {
		sessions: Session[];
		sid?: string | null;
		loadingSessions?: boolean;
		openingId?: string | null;
		deletingId?: string | null;
		chars: ShowcaseChar[];
		charsLoading?: boolean;
		uid: string;
		onNew: () => void;
		onOpen: (id: string) => void;
		onDelete: (id: string) => void;
		onUidChange: (uid: string) => void;
	} = $props();

	let query = $state('');
	let tab = $state<'chats' | 'persos'>('chats');

	let q = $derived(query.trim().toLowerCase());
	let filteredSessions = $derived(
		q ? sessions.filter((s) => (s.title || 'Conversation').toLowerCase().includes(q)) : sessions
	);
	let filteredChars = $derived(
		q ? chars.filter((c) => c.name.toLowerCase().includes(q)) : chars
	);
</script>

<div class="flex min-h-0 flex-1 flex-col">
	<div class="shrink-0 px-3 pt-3 pb-1">
		<label class="flex h-11 items-center gap-2 rounded-control bg-inset px-2.5 shadow-hairline sm:h-8">
			<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true" class="shrink-0 text-ink-3"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
			<input
				bind:value={query}
				placeholder={tab === 'chats' ? 'Rechercher' : 'Filtrer persos'}
				aria-label="Filtrer l'onglet courant"
				class="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-3"
			/>
			{#if q}
				<button
					type="button"
					onclick={() => (query = '')}
					class="flex size-6 shrink-0 items-center justify-center rounded-md text-ink-3 hover:bg-hover hover:text-ink"
					aria-label="Effacer la recherche">×</button
				>
			{/if}
		</label>

		<button
			type="button"
			onclick={onNew}
			class="rc-press rc-btn-primary mt-1.5 flex min-h-11 w-full items-center gap-2 rounded-full px-5 text-[15px] font-semibold sm:min-h-11"
		>
			<span class="min-w-0 flex-1 truncate text-left">Nouveau chat</span>
			<span class="shrink-0" aria-hidden="true">→</span>
		</button>
		<button
			type="button"
			onclick={() => goto('/vitrine')}
			class="rc-chip rc-btn-outline mt-1 flex min-h-11 w-full items-center gap-2 rounded-full px-5 text-[15px] font-semibold sm:min-h-11"
		>
			<span class="min-w-0 flex-1 truncate text-left">Vitrine</span>
			<span class="shrink-0" aria-hidden="true">→</span>
		</button>
		<button
			type="button"
			onclick={() => goto('/news')}
			class="rc-chip mt-1 flex min-h-11 w-full items-center gap-2 rounded-full bg-surface px-5 text-[15px] font-medium text-ink-2 shadow-hairline hover:text-ink sm:min-h-11"
		>
			<span class="min-w-0 flex-1 truncate text-left">News patch</span>
			<span class="shrink-0 text-xs text-ink-3" aria-hidden="true">→</span>
		</button>

		<div class="mt-1.5 flex rounded-full bg-inset p-0.5 shadow-hairline" role="tablist" aria-label="Contenu du panneau">
			{#each [['chats', `Chats${sessions.length ? ` · ${sessions.length}` : ''}`], ['persos', `Persos${chars?.length ? ` · ${chars.length}` : ''}`]] as [v, label]}
				<button
					type="button"
					role="tab"
					aria-selected={tab === v}
					onclick={() => (tab = v as 'chats' | 'persos')}
					class="rc-press min-h-9 flex-1 rounded-full text-[13px] font-medium {tab === v
						? 'bg-surface text-ink shadow-btn'
						: 'text-ink-3 hover:text-ink-2'}">{label}</button
				>
			{/each}
		</div>
	</div>

	{#if tab === 'chats'}
		<div class="flex min-h-0 flex-1 flex-col px-3 pt-1 pb-3">
			<div class="min-h-0 flex-1 overflow-y-auto pb-1">
				{#if loadingSessions}
					<div class="flex flex-col gap-1.5 px-0.5 py-1" role="status" aria-label="Chargement des conversations">
						{#each Array(4) as _, i}
							<div
								class="rounded-control bg-field px-3 py-3"
								style="animation:fade-up 320ms cubic-bezier(0.23,1,0.32,1) {i * 60}ms both"
							>
								<div class="h-3 w-2/3 rounded bg-line"></div>
								<div class="mt-2 h-2 w-1/3 rounded bg-line"></div>
							</div>
						{/each}
					</div>
				{:else}
				{#each filteredSessions as s (s.id)}
					<div
						class="group mb-0.5 flex items-center gap-1 rounded-control border px-2 py-1 {sid === s.id || openingId === s.id
							? 'border-sport/30 bg-sport/10'
							: 'border-transparent hover:bg-hover'}"
					>
						<a
							href={`/c/${s.id}`}
							class="min-w-0 flex-1 py-1 text-left {openingId === s.id ? 'pointer-events-none opacity-60' : ''}"
							aria-busy={openingId === s.id}
							onclick={(e) => {
								e.preventDefault();
								onOpen(s.id);
							}}
						>
							<span class="block truncate text-[13px] font-medium text-ink">
								{openingId === s.id ? 'Chargement…' : s.title || 'Conversation'}
							</span>
							<span class="block text-[11px] text-ink-3 tabular-nums">{s.n} msgs</span>
						</a>
						<button
							type="button"
							disabled={deletingId === s.id}
							class="flex size-9 shrink-0 items-center justify-center rounded-md text-xs text-ink-3 hover:text-red disabled:opacity-60 sm:size-7 sm:opacity-0 sm:group-hover:opacity-100"
							title="Supprimer"
							aria-label={`Supprimer ${s.title || 'conversation'}`}
							onclick={() => onDelete(s.id)}>{deletingId === s.id ? '…' : '✕'}</button
						>
					</div>
				{:else}
					<p class="px-2 py-1 text-xs text-ink-3">
						{q ? 'Aucun résultat.' : 'Aucune conversation.'}
					</p>
				{/each}
				{/if}
			</div>
		</div>
	{:else}
		<div class="flex min-h-0 flex-1 flex-col px-3 pt-1 pb-3">
			<div class="min-h-0 flex-1 overflow-y-auto pb-1">
				{#if charsLoading}
					<p class="px-2 py-1 text-xs text-ink-3" role="status">Chargement vitrine…</p>
				{:else}
					{#each filteredChars as c (c.id)}
						<div class="mb-0.5 rounded-control border border-transparent px-2 py-1.5 hover:bg-hover">
							<span class="block truncate text-[13px] font-medium text-ink">
								<span
									class="mr-1 inline-block size-2 rounded-full align-middle"
									style="background:{rarColor(c.rarity)}"
									aria-hidden="true"
								></span>{c.name} · {c.level}
							</span>
							<span class="block text-[11px] text-ink-3 tabular-nums">
								{c.rarity}★{c.crit_rate ? ` · crit ${c.crit_rate.toFixed(0)}/${(c.crit_dmg ?? 0).toFixed(0)}` : ''}{(c.findings?.length ?? 0) ? ` · ${c.findings?.length} pt` : ''}
							</span>
						</div>
					{:else}
						<p class="px-2 py-1 text-xs text-ink-3">
							{q ? 'Aucun résultat.' : 'Vitrine vide.'}
						</p>
					{/each}
				{/if}
			</div>
		</div>
	{/if}

	<!-- UID -->
	<div class="shrink-0 border-t border-line p-2.5">
		<label class="block px-1.5 text-[11px] font-medium tracking-[0.08em] text-ink-3 uppercase" for="gc-uid">UID (EU)</label>
		<input
			id="gc-uid"
			value={uid}
			inputmode="numeric"
			onchange={(e) => onUidChange(e.currentTarget.value.trim())}
			class="mt-1 w-full rounded-control bg-inset px-2.5 py-2 font-mono text-[13px] text-ink shadow-hairline outline-none"
		/>
	</div>
</div>
