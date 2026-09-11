<script lang="ts">
	let {
		draft = $bindable(''),
		busy = false,
		selectedLabel = null,
		onSend,
		onClearSelected,
		images = $bindable<string[]>([])
	}: {
		draft: string;
		busy?: boolean;
		selectedLabel?: string | null;
		onSend: () => void;
		onClearSelected: () => void;
		images?: string[];
	} = $props();

	let ta: HTMLTextAreaElement | null = $state(null);
	let fileInput: HTMLInputElement | null = $state(null);
	let imgError = $state('');

	const IMG_MAX = 2;
	const IMG_SIDE = 1024;

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

	function removeAt(i: number) {
		images = images.filter((_, j) => j !== i);
		imgError = '';
	}

	async function compress(file: File): Promise<string> {
		const bmp = await createImageBitmap(file);
		const scale = Math.min(1, IMG_SIDE / Math.max(bmp.width, bmp.height));
		const w = Math.max(1, Math.round(bmp.width * scale));
		const h = Math.max(1, Math.round(bmp.height * scale));
		const canvas = document.createElement('canvas');
		canvas.width = w;
		canvas.height = h;
		const ctx = canvas.getContext('2d');
		if (!ctx) throw new Error('canvas indisponible');
		ctx.drawImage(bmp, 0, 0, w, h);
		bmp.close();
		const blob: Blob | null = await new Promise((res) =>
			canvas.toBlob(res, 'image/jpeg', 0.8)
		);
		if (!blob) throw new Error('compression impossible');
		const buf = await blob.arrayBuffer();
		let bin = '';
		const bytes = new Uint8Array(buf);
		for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
		return `data:image/jpeg;base64,${btoa(bin)}`;
	}

	async function addFiles(list: FileList | File[]) {
		imgError = '';
		const files = [...list].filter((f) => f.type.startsWith('image/'));
		if (!files.length) {
			imgError = 'Fichier non image ignoré (jpeg/png/webp/gif).';
			return;
		}
		for (const f of files) {
			if (images.length >= IMG_MAX) {
				imgError = `Max ${IMG_MAX} images par message.`;
				break;
			}
			try {
				const url = await compress(f);
				if (url.length > 2_000_000) {
					imgError = 'Image trop lourde même compressée (~1 Mo max).';
					continue;
				}
				images = [...images, url];
			} catch {
				imgError = 'Lecture image impossible, réessaie avec un autre fichier.';
			}
		}
		if (fileInput) fileInput.value = '';
	}

	function onPaste(e: ClipboardEvent) {
		const files = [...(e.clipboardData?.files ?? [])].filter((f) =>
			f.type.startsWith('image/')
		);
		if (files.length) {
			e.preventDefault();
			addFiles(files);
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
	{#if images.length > 0}
		<div class="flex flex-wrap gap-1.5 px-1 pt-1 pb-2">
			{#each images as url, i}
				<span class="relative inline-block">
					<img
						src={url}
						alt="Capture jointe {i + 1}"
						class="h-16 w-16 rounded-xl border border-line object-cover"
					/>
					<button
						type="button"
						onclick={() => removeAt(i)}
						class="absolute -top-1.5 -right-1.5 flex size-6 items-center justify-center rounded-full bg-ink text-sm leading-none text-[var(--surface)] shadow-btn"
						aria-label="Retirer l'image {i + 1}">×</button
					>
				</span>
			{/each}
		</div>
	{/if}
	{#if imgError}
		<p class="px-2 pb-1 text-xs text-ink-3" role="alert">{imgError}</p>
	{/if}
	<div class="flex items-end gap-1.5">
		<input
			bind:this={fileInput}
			type="file"
			accept="image/jpeg,image/png,image/webp,image/gif"
			multiple
			class="hidden"
			aria-label="Joindre des images"
			onchange={(e) => addFiles((e.target as HTMLInputElement).files ?? [])}
		/>
		<button
			type="button"
			onclick={() => fileInput?.click()}
			disabled={busy || images.length >= IMG_MAX}
			class="rc-press mb-1 flex size-11 shrink-0 items-center justify-center rounded-full text-ink-3 hover:bg-hover hover:text-ink disabled:opacity-30"
			aria-label="Joindre une image"
			title="Joindre jusqu'à 2 captures (compressées ~1 Mo)"
		>
			<svg
				width="17"
				height="17"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M21 11.5l-8.5 8.5a5.5 5.5 0 0 1-7.8-7.8L13 4a3.7 3.7 0 0 1 5.2 5.2l-8.2 8.2a1.85 1.85 0 0 1-2.6-2.6L14.5 7.7" />
			</svg>
		</button>
		<textarea
			bind:this={ta}
			rows="2"
			bind:value={draft}
			disabled={busy}
			placeholder="Que veux-tu optimiser : builds, teams, progression…"
			aria-label="Message"
			onkeydown={keydown}
			oninput={autoresize}
			onpaste={onPaste}
			class="max-h-40 min-h-11 w-full min-w-0 flex-1 resize-none bg-transparent px-2.5 py-2.5 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-3 disabled:opacity-50"
		></textarea>
		<span
			class="mb-2 hidden shrink-0 items-center rounded-full bg-field px-2.5 py-1 font-mono text-[10.5px] whitespace-nowrap text-ink-3"
			title="Modèle côté serveur (OMNIROUTE_MODEL)">go</span
		>
		<button
			type="button"
			onclick={onSend}
			disabled={busy || (!draft.trim() && images.length === 0)}
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
