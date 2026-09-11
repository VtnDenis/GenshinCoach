import { marked } from 'marked';
import katex from 'katex';
import DOMPurify from 'dompurify';

// ponytail: maths protégées AVANT marked (sinon tableaux/$ manglés), rendues APRÈS via KaTeX.

interface MathChunk {
	tex: string;
	display: boolean;
}

const esc = (s: string) =>
	s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const isOpenPrev = (ch: string | undefined) =>
	ch === undefined || /[\s\(\[{>*"'_\-—,:;!?/]/.test(ch);
const isCloseNext = (ch: string | undefined) =>
	ch === undefined || /[\s\)\]}.,:;!?'"_—%‰/]/.test(ch);

/** Découpe src en texte markdown (maths/code protégés) + chunks LaTeX hors code. */
function extract(src: string): { md: string; maths: MathChunk[] } {
	const maths: MathChunk[] = [];
	let md = '';
	let i = 0;
	const n = src.length;
	const push = (tex: string, display: boolean) => {
		maths.push({ tex, display });
		md += display ? `\n\n@@RC-MATH-${maths.length - 1}@@\n\n` : `@@RC-MATH-${maths.length - 1}@@`;
	};
	while (i < n) {
		// Bloc clôturé ``` / ~~~ : copié verbatim (pas de maths dedans)
		const fence =
			(i === 0 || src[i - 1] === '\n') && (src[i] === '`' || src[i] === '~')
				? src.slice(i).match(/^(`{3,}|~{3,})[^\n]*\n/)
				: null;
		if (fence) {
			const ch = fence[1][0];
			const run = fence[1].length;
			const closeRe = new RegExp(`\n${ch}{${run},}[ \\t]*(\\n|$)`);
			const rest = src.slice(i + fence[0].length);
			const m = closeRe.exec(rest);
			const end = m ? i + fence[0].length + m.index + m[0].length : n;
			md += src.slice(i, end);
			i = end;
			continue;
		}
		// Code inline `...` : verbatim
		if (src[i] === '`') {
			let k = 0;
			while (src[i + k] === '`') k++;
			const close = src.indexOf('`'.repeat(k), i + k);
			const end = close === -1 ? n : close + k;
			md += src.slice(i, end);
			i = end;
			continue;
		}
		// Display $$...$$ ou \[...\]
		let fenced = false;
		for (const [open, close] of [['$$', '$$'], ['\\[', '\\]']] as const) {
			if (!src.startsWith(open, i)) continue;
			fenced = true;
			const j = src.indexOf(close, i + open.length);
			const tex = j === -1 ? '' : src.slice(i + open.length, j).trim();
			if (j !== -1 && tex) {
				push(tex, true);
				i = j + close.length;
			} else {
				md += open;
				i += open.length;
			}
		}
		if (fenced) continue;
		// Inline \(...\)
		if (src.startsWith('\\(', i)) {
			const j = src.indexOf('\\)', i + 2);
			const tex = j === -1 ? '' : src.slice(i + 2, j).trim();
			if (j !== -1 && tex) {
				push(tex, false);
				i = j + 2;
			} else {
				md += '\\(';
				i += 2;
			}
			continue;
		}
		// Inline $...$ (garde prix "10$" intacts : open suit non-espace, close précède non-espace)
		if (src[i] === '$' && src[i + 1] !== '$' && isOpenPrev(src[i - 1])) {
			const nxt = src[i + 1];
			if (nxt !== undefined && !/[\s]/.test(nxt)) {
				let j = i + 1;
				let found = -1;
				while (j < n && j - i < 500) {
					if (src[j] === '$' && src[j - 1] !== '\\' && src[j + 1] !== '$') {
						const prev = src[j - 1];
						if (prev !== undefined && !/[\s]/.test(prev) && isCloseNext(src[j + 1])) {
							found = j;
							break;
						}
					}
					if (src[j] === '\n' && src[j + 1] === '\n') break; // reste dans le paragraphe
					j++;
				}
				if (found !== -1) {
					const tex = src.slice(i + 1, found).trim();
					if (tex && !/^\d+(\.\d+)?$/.test(tex)) {
						push(tex, false);
						i = found + 1;
						continue;
					}
				}
			}
		}
		md += src[i];
		i++;
	}
	return { md, maths };
}

function renderTex(tex: string, display: boolean): string {
	try {
		return katex.renderToString(tex, { displayMode: display, throwOnError: false, strict: false });
	} catch {
		return `<code>${esc(tex)}</code>`;
	}
}

function stripToolLeak(src: string): string {
	if (!src) return src;
	const low = src.toLowerCase();
	if (!low.includes('<function') && !low.includes('<parameter')) return src;
	const i = low.indexOf('<function');
	if (i !== -1) return src.slice(0, i).trimEnd();
	const j = low.indexOf('<parameter');
	return j !== -1 ? src.slice(0, j).trimEnd() : src;
}

/** Rendu complet GFM (tableaux, code, listes…) + LaTeX $..$/$$..$$, sanitizé. */
export function renderMd(src: string): string {
	if (!src) return '';
	src = stripToolLeak(src);
	const { md, maths } = extract(src);
	let html = marked.parse(md, { gfm: true, breaks: true }) as string;
	for (let k = 0; k < maths.length; k++) {
		const m = maths[k];
		const out = renderTex(m.tex, m.display);
		if (m.display) {
			const p = `<p>@@RC-MATH-${k}@@</p>`;
			html = html.includes(p)
				? html.replace(p, `<div class="katex-block">${out}</div>`)
				: html.replaceAll(`@@RC-MATH-${k}@@`, `<div class="katex-block">${out}</div>`);
		} else {
			html = html.replaceAll(`@@RC-MATH-${k}@@`, out);
		}
	}
	html = html
		.replace(/<a\s+(?![^>]*target=)href=/g, '<a target="_blank" rel="noopener noreferrer" href=')
		.replace(/<table>/g, '<div class="md-table"><table>')
		.replace(/<\/table>/g, '</table></div>');
	// ponytail: prerender SSR sans window et sans contenu user -> sanitize au runtime client uniquement
	if (typeof window === 'undefined') return html;
	return DOMPurify.sanitize(html, {
		ADD_TAGS: [
			'math', 'semantics', 'annotation', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub',
			'mfrac', 'msqrt', 'mroot', 'mtext', 'mtable', 'mtr', 'mtd', 'menclose',
			'mstyle', 'mpadded', 'mphantom', 'mglyph'
		],
		ADD_ATTR: ['class', 'target', 'rel', 'aria-hidden', 'aria-label', 'display', 'xmlns', 'encoding']
	}) as string;
}
