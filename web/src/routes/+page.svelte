<script lang="ts">
	import { onMount, tick } from 'svelte';
	import {
		fetchShowcase,
		sendChat,
		sendChatStream,
		listSessions,
		getMessages,
		deleteSession,
		getUid,
		setUid,
		getSid,
		setSid,
		renderMd,
		type Msg,
		type MsgStats,
		type Session,
		type Showcase,
		type ShowcaseChar
	} from '$lib/api';
	import SidebarNav from '$lib/components/SidebarNav.svelte';
	import Thinking from '$lib/components/Thinking.svelte';
	import ThinkingTrace from '$lib/components/ThinkingTrace.svelte';
	import CoachMessage from '$lib/components/CoachMessage.svelte';
	import PromptBar from '$lib/components/PromptBar.svelte';
	import LoadingState from '$lib/components/LoadingState.svelte';
	import Wordmark from '$lib/components/Wordmark.svelte';
	import { rise } from '$lib/motion';

	let msgs: Msg[] = $state([]);
	let draft = $state('');
	let busy = $state(false);
	let sessions: Session[] = $state([]);
	let showcase = $state<Showcase | null>(null);
	let charsLoading = $state(true);
	let uid = $state('702342940');
	let sid: string | null = $state(null);
	let currentTitle = $derived(
		sessions.find((s) => s.id === sid)?.title ||
			(msgs.length ? 'Conversation' : 'Nouveau chat')
	);
	let chars: ShowcaseChar[] = $derived(showcase ? showcase.characters.length ? showcase.characters : showcase.preview : []);
	let threadEl: HTMLElement | null = $state(null);
	let showJump = $state(false);
	let dark = $state(false);
	let drawerOpen = $state(false);
	let sideCollapsed = $state(false);
	let notFound = $state(false);
	let copied = $state(false);
	let openingId = $state<string | null>(null);
	let deletingId = $state<string | null>(null);
	let loadingSessions = $state(true);
	let sessionsError = $state('');
	let streaming = $state(false);

	let { initialSid = null }: { initialSid?: string | null } = $props();

	const SUGGESTIONS = [
		'Que monter en prio cette semaine ?',
		'Quelle team avec mon roster ?',
		'Résume mon compte en 5 lignes',
		'Je bloque en donjon, que faire ?',
		'News du patch actuel ?'
	];

	onMount(() => {
		dark = document.documentElement.classList.contains('dark');
		try {
			uid = getUid();
			sideCollapsed = localStorage.getItem('gc:side') === 'hidden';
		} catch {
			/* private mode */
		}
		boot();
		const onPop = () => {
			const id = sidFromUrl();
			if (id === sid) return;
			if (id && sessions.some((s) => s.id === id)) openSession(id, true);
			else if (id) {
				notFound = true;
				sid = null;
				msgs = [];
			} else newChat();
		};
		window.addEventListener('popstate', onPop);
		return () => window.removeEventListener('popstate', onPop);
	});

	function sidFromUrl(): string | null {
		try {
			const m = window.location.pathname.match(/^\/c\/([A-Za-z0-9_-]+)\/?$/);
			return m ? m[1] : initialSid;
		} catch {
			return initialSid;
		}
	}

	function syncUrl(replace = false) {
		try {
			const want = sid ? `/c/${sid}` : '/';
			if (window.location.pathname !== want)
				window.history[replace ? 'replaceState' : 'pushState']({}, '', want);
		} catch {
			/* SSR-safe */
		}
	}

	function toggleDark() {
		dark = !dark;
		document.documentElement.classList.toggle('dark', dark);
		try {
			localStorage.setItem('theme', dark ? 'dark' : 'light');
		} catch {
			/* private mode */
		}
	}

	function toggleSide() {
		sideCollapsed = !sideCollapsed;
		try {
			localStorage.setItem('gc:side', sideCollapsed ? 'hidden' : 'shown');
		} catch {
			/* private mode */
		}
	}

	async function boot() {
		await Promise.all([refreshSessions(), refreshShowcase()]);
		const id = sidFromUrl() || getSid();
		if (id && sessions.some((s) => s.id === id)) await openSession(id, true);
	}

	async function refreshSessions() {
		try {
			const r = await listSessions();
			sessions = r.sessions;
			sessionsError = '';
		} catch (e) {
			// Historique indisponible (BDD KO, backend éteint…) : on l'affiche au lieu de "Aucune conversation".
			sessionsError = (e as Error).message;
		} finally {
			loadingSessions = false;
		}
	}

	async function refreshShowcase() {
		charsLoading = true;
		try {
			showcase = await fetchShowcase(uid);
		} catch {
			showcase = null;
		} finally {
			charsLoading = false;
		}
	}

	function onUidChange(v: string) {
		if (!v || v === uid) return;
		uid = v;
		setUid(v);
		refreshShowcase();
	}

	function newChat() {
		sid = null;
		setSid(null);
		msgs = [];
		notFound = false;
		syncUrl();
	}

	async function openSession(id: string, replace = false) {
		openingId = id;
		notFound = false;
		try {
			const r = await getMessages(id);
			msgs = r.messages.map((m) => {
				const out = m.out_tokens ?? null;
				const asec = m.answer_secs ?? null;
				return {
					role: m.role === 'user' ? 'user' : 'assistant',
					text: m.content,
					thinking: m.thinking ?? null,
					thinkSecs: m.secs ?? null,
					stats:
						out != null || asec != null
							? {
									totalS: asec,
									toks: out != null && asec ? Math.round((out / asec) * 10) / 10 : null,
									out
								}
							: null
				};
			});
			sid = id;
			setSid(id);
			syncUrl(replace);
			scrollBottom();
		} catch {
			notFound = true;
		} finally {
			openingId = null;
		}
	}

	async function delSession(id: string) {
		deletingId = id;
		try {
			await deleteSession(id);
			sessions = sessions.filter((s) => s.id !== id);
			if (sid === id) newChat();
		} finally {
			deletingId = null;
		}
	}

	function scrollBottom() {
		tick().then(() => {
			if (threadEl) threadEl.scrollTop = threadEl.scrollHeight;
		});
	}

	function updateJump() {
		if (!threadEl) return;
		showJump = threadEl.scrollHeight - threadEl.scrollTop - threadEl.clientHeight > 120;
	}

	function jumpToBottom() {
		if (threadEl) threadEl.scrollTo({ top: threadEl.scrollHeight, behavior: 'smooth' });
	}

	async function send() {
		const q = draft.trim();
		if (!q || busy) return;
		draft = '';
		msgs = [...msgs, { role: 'user', text: q }];
		busy = true;
		scrollBottom();
		msgs = [...msgs, { role: 'assistant', text: '' }];
		const idx = msgs.length - 1;
		let streamed = '';
		let streamedThinking = '';
		streaming = false;
		const paint = (t: string) => {
			streamed += t;
			streaming = true;
			msgs = msgs.map((m, i) => (i === idx ? { ...m, text: streamed } : m));
			scrollBottom();
		};
		const paintThinking = (t: string) => {
			streamedThinking += t;
			msgs = msgs.map((m, i) => (i === idx ? { ...m, thinking: streamedThinking } : m));
		};
		const finish = (
			text: string,
			model?: string | null,
			thinking?: string | null,
			thinkSecs?: number | null,
			stats?: MsgStats | null
		) => {
			if (!text.trim()) text = 'Erreur : réponse vide du coach, réessaie.';
			msgs = msgs.map((m, i) =>
				i === idx
					? {
							role: 'assistant',
							text,
							model: model ?? m.model,
							thinking: thinking ?? m.thinking ?? null,
							thinkSecs: thinkSecs ?? m.thinkSecs ?? null,
							stats: stats ?? m.stats ?? null
						}
					: m
			);
		};
		try {
			try {
				const r = await sendChatStream(q, uid, sid, paint, paintThinking);
				sid = r.session_id;
				setSid(sid);
				finish(r.answer || streamed, r.model, r.thinking || streamedThinking || null, r.thinkSecs, r.stats);
			} catch (e) {
				if (streamed) throw e; // partiel déjà affiché : on ajoute l'erreur dessous
				const r = await sendChat(q, uid, sid); // repli batch
				sid = r.session_id;
				setSid(sid);
				finish(r.answer, r.model, r.thinking || null, null, {
					totalS: r.stats.total_s,
					toks: r.stats.toks,
					out: r.stats.out
				});
			}
			syncUrl(true);
			refreshSessions();
		} catch (e) {
			finish(streamed ? `${streamed}\n\nErreur : ${(e as Error).message}` : `Erreur : ${(e as Error).message}`);
		} finally {
			busy = false;
			streaming = false;
			scrollBottom();
		}
	}

	function copyLink() {
		try {
			navigator.clipboard.writeText(window.location.href);
			copied = true;
			setTimeout(() => (copied = false), 1400);
		} catch {
			/* clipboard indisponible */
		}
	}

	function exportMd() {
		const body = msgs.map((m) => (m.role === 'user' ? `## Joueur\n\n${m.text}` : `## Coach\n\n${m.text}`)).join('\n\n');
		const blob = new Blob([`# GenshinCoach — conversation\n\n${body}\n`], { type: 'text/markdown' });
		const a = document.createElement('a');
		a.href = URL.createObjectURL(blob);
		a.download = `genshincoach-${sid ?? 'chat'}.md`;
		a.click();
		URL.revokeObjectURL(a.href);
	}
</script>

<div class="flex h-[100dvh] flex-col bg-page text-ink">
	<header class="rc-sportline flex shrink-0 items-center gap-1 border-b border-line bg-surface-warm px-2 sm:px-3">
		<button
			type="button"
			onclick={() => (drawerOpen ? (drawerOpen = false) : sideCollapsed ? toggleSide() : (drawerOpen = true))}
			class="flex size-11 items-center justify-center rounded-control text-ink-3 hover:bg-hover hover:text-ink lg:hidden"
			aria-label="Ouvrir le menu"
		>
			<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
		</button>
		<button
			type="button"
			onclick={toggleSide}
			class="hidden size-11 items-center justify-center rounded-control text-ink-3 hover:bg-hover hover:text-ink lg:flex"
			aria-label={sideCollapsed ? 'Afficher le panneau' : 'Masquer le panneau'}
		>
			<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
		</button>
		<div class="flex min-w-0 flex-1 items-center gap-2 py-2">
			<Wordmark class="text-[18px]" />
			<h1 class="hidden min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight lg:block">
				{currentTitle}
			</h1>
		</div>
		<button
			type="button"
			onclick={toggleDark}
			class="flex size-11 items-center justify-center rounded-control text-ink-3 hover:bg-hover hover:text-ink"
			aria-label={dark ? 'Passer en mode clair' : 'Passer en mode sombre'}
		>
			{#if dark}
				<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
			{:else}
				<svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
			{/if}
		</button>
	</header>

	<div class="relative flex min-h-0 flex-1">
		<!-- desktop sidebar -->
		<aside class="hidden w-72 shrink-0 flex-col border-r border-line bg-surface-warm {sideCollapsed ? '' : 'lg:flex'}">
			<SidebarNav
				{sessions}
				{sid}
				{loadingSessions}
				{openingId}
				{deletingId}
				{chars}
				{charsLoading}
				{uid}
				onNew={newChat}
				onOpen={(id) => openSession(id)}
				onDelete={(id) => delSession(id)}
				onUidChange={onUidChange}
			/>
		</aside>

		<!-- mobile drawer -->
		{#if drawerOpen}
			<div class="absolute inset-0 z-40 lg:hidden">
				<button
					type="button"
					class="absolute inset-0 bg-black/40"
					aria-label="Fermer le menu"
					onclick={() => (drawerOpen = false)}
				></button>
				<div
					use:rise
					class="absolute inset-y-0 left-0 flex w-[86vw] max-w-80 flex-col overflow-y-auto bg-surface-warm pt-3 shadow-overlay"
					role="dialog"
					aria-label="Panneau latéral"
				>
					<SidebarNav
						{sessions}
						{sid}
						{loadingSessions}
						{openingId}
						{deletingId}
						{chars}
						{charsLoading}
						{uid}
						onNew={() => {
							drawerOpen = false;
							newChat();
						}}
						onOpen={(id) => {
							drawerOpen = false;
							openSession(id);
						}}
						onDelete={(id) => delSession(id)}
						onUidChange={onUidChange}
					/>
				</div>
			</div>
		{/if}

		<main class="flex min-w-0 flex-1 flex-col">
			<div bind:this={threadEl} onscroll={updateJump} class="min-h-0 flex-1 overflow-y-auto">
				<div class="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-4 sm:gap-5 sm:px-6 sm:py-6">
					{#if openingId}
						<div role="status" aria-label="Chargement de la conversation">
							<LoadingState label="Conversation" />
							<div class="mt-3 flex flex-col gap-3" aria-hidden="true">
								<div class="ml-auto h-10 w-2/3 rounded-card rounded-br-md bg-field"></div>
								<div class="h-20 rounded-card border border-line bg-surface"></div>
								<div class="ml-auto h-10 w-1/2 rounded-card rounded-br-md bg-field"></div>
								<div class="h-20 rounded-card border border-line bg-surface"></div>
							</div>
						</div>
					{:else if msgs.length === 0 && !busy}
						<div use:rise class="relative overflow-hidden py-4 sm:py-6">
							<svg
								class="pointer-events-none absolute -top-2 -right-8 w-64 opacity-30 sm:w-80"
								viewBox="0 0 300 110"
								fill="none"
								aria-hidden="true"
							>
								<path
									d="M8 92 C 50 86, 58 30, 100 38 S 150 100, 192 66 S 252 12, 292 34"
									stroke="var(--sport)"
									stroke-width="3.5"
									stroke-linecap="round"
								/>
								<circle cx="8" cy="92" r="5" fill="var(--sport)" />
								<circle cx="292" cy="34" r="5" fill="none" stroke="var(--sport)" stroke-width="3" />
							</svg>
							<div class="relative">
								{#if showcase}
									<p class="font-mono text-[11px] tracking-[0.16em] text-sport uppercase">
										{showcase.player.nickname} — AR{showcase.player.level} WL{showcase.player.worldLevel}
									</p>
									<p class="rc-numerals mt-1 text-ink tabular-nums [font-size:clamp(4.5rem,17vw,9rem)]" aria-label={`${chars.length} personnages en vitrine`}>
										{chars.length}<span class="ml-3 font-mono text-sm tracking-[0.2em] text-ink-3">PERSOS</span>
									</p>
									<p class="mt-1 font-mono text-xs text-ink-2">
										{chars.slice(0, 4).map((c) => `${c.name} ${c.level}`).join(' · ')}
									</p>
								{:else}
									<p class="font-mono text-[11px] tracking-[0.16em] text-sport uppercase">
										GenshinCoach
									</p>
									<p class="rc-numerals mt-1 text-ink [font-size:clamp(4.5rem,17vw,9rem)]">
										ON Y VA.
									</p>
									<p class="mt-1 font-mono text-xs text-ink-2">
										Renseigne ton UID dans le panneau pour voir ta vitrine ici.
									</p>
								{/if}
								<h2 class="mt-4 text-xl font-semibold tracking-tight text-ink">
									Qu'est-ce qu'on optimise aujourd'hui ?
								</h2>
								<div class="mt-3 flex flex-wrap gap-1.5">
									{#each SUGGESTIONS as s}
										<button
											type="button"
											onclick={() => {
												draft = s;
											}}
											class="rc-chip min-h-11 rounded-full bg-surface px-3.5 text-[13px] text-ink-2 shadow-btn hover:text-ink sm:min-h-9"
										>
											{s}
										</button>
									{/each}
								</div>
								<p class="mt-3 hidden text-xs text-ink-3 lg:block">
									Ouvre la page Vitrine pour l'audit détaillé de tes builds.
								</p>
								<button
									type="button"
									class="rc-press mt-3 min-h-11 text-[13px] font-medium text-accent-ink underline underline-offset-2 lg:hidden"
									onclick={() => (drawerOpen = true)}
								>
									Voir vitrine et conversations
								</button>
							</div>
						</div>
					{/if}
					{#if notFound}
						<div class="rounded-window bg-canvas p-4 shadow-hairline sm:p-5">
							<p class="text-sm leading-relaxed text-ink">
								<strong class="font-semibold">Conversation introuvable.</strong>
								Elle a peut-être été supprimée.
								<button
									type="button"
									onclick={newChat}
									class="font-medium text-accent-ink underline underline-offset-2"
								>
									Démarrer une nouvelle conversation
								</button>
							</p>
						</div>
					{/if}
					{#if sessionsError}
						<div class="rounded-window bg-canvas p-4 shadow-hairline sm:p-5" role="alert">
							<p class="text-sm leading-relaxed text-ink">
								<strong class="font-semibold">Historique indisponible.</strong>
								{sessionsError}
							</p>
						</div>
					{/if}
					{#if msgs.length > 0}
						<div class="flex justify-end gap-1">
							{#if sid}
								<button
									type="button"
									onclick={copyLink}
									class="min-h-7 rounded-md px-2 text-xs text-ink-3 hover:bg-hover hover:text-ink-2"
								>
									{copied ? 'Lien copié ✓' : 'Copier le lien'}
								</button>
							{/if}
							<button
								type="button"
								onclick={exportMd}
								class="min-h-7 rounded-md px-2 text-xs text-ink-3 hover:bg-hover hover:text-ink-2"
							>
								Exporter .md
							</button>
						</div>
					{/if}
					{#each msgs as m, i (i + '-' + m.role)}
						<div use:rise class="w-full {m.role === 'user' ? 'flex justify-end' : ''}">
							{#if m.role === 'user'}
								<p
									class="max-w-[88%] rounded-card rounded-br-md bg-ink px-3.5 py-2.5 text-sm whitespace-pre-wrap text-[var(--surface)] shadow-btn sm:max-w-[75%]"
								>
									{m.text}
								</p>
							{:else}
								<div class="w-full min-w-0">
									{#if !m.text && busy && i === msgs.length - 1}
										<div class="rounded-card border border-line bg-surface px-4 py-3">
											<LoadingState label="Coach écrit" />
										</div>
									{:else}
										{#if m.thinking}
											<ThinkingTrace
												text={m.thinking}
												secs={m.thinkSecs ?? null}
												streaming={busy && streaming && i === msgs.length - 1}
											/>
										{/if}
										<CoachMessage
											text={m.text || 'Erreur : réponse vide du coach, réessaie.'}
											model={m.model}
											stats={m.stats ?? null}
										/>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
					{#if busy && !streaming}
						<div use:rise class="w-full">
							<div class="rounded-card border border-line bg-surface px-4 py-3">
								<Thinking rows={[]} working={true} activeLabel="Analyse de ta vitrine…" />
								<div class="mt-2 border-t border-line pt-2.5">
									<LoadingState label="Coach" />
								</div>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<div class="relative shrink-0">
				{#if showJump}
					<button
						type="button"
						onclick={jumpToBottom}
						aria-label="Aller en bas"
						class="absolute -top-11 left-1/2 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-line bg-surface text-ink-2 shadow-btn hover:bg-hover hover:text-ink"
					>
						<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
					</button>
				{/if}
				<div class="mx-auto w-full max-w-3xl px-3 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6">
					<PromptBar
						bind:draft
						{busy}
						selectedLabel={null}
						onSend={send}
						onClearSelected={() => {}}
					/>
				</div>
			</div>
		</main>
	</div>
</div>
