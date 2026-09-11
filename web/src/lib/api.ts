export interface Session {
	id: string;
	title: string;
	updated_at: number;
	n: number;
}

export interface StoredMsg {
	role: string;
	content: string;
	created_at: number;
	thinking?: string | null;
	secs?: number | null;
	answer_secs?: number | null;
	out_tokens?: number | null;
}

export interface Step {
	tool: string;
	ms?: number | null;
	result?: string;
	error?: string;
}

export interface MsgStats {
	totalS?: number | null;
	toks?: number | null;
	out?: number | null;
}

export interface Msg {
	role: 'user' | 'assistant';
	text: string;
	model?: string | null;
	thinking?: string | null;
	thinkSecs?: number | null;
	stats?: MsgStats | null;
	steps?: Step[] | null;
}

export const fmtDur = (s: number | null | undefined): string | null => {
	if (s == null || !isFinite(s) || s < 0) return null;
	if (s < 60) return `${Math.round(s)}s`;
	const m = Math.floor(s / 60);
	return `${m}m ${String(Math.round(s % 60)).padStart(2, '0')}s`;
};

export interface ShowcaseChar {
	id: string;
	name: string;
	element: string;
	rarity: number;
	level: number;
	crit_rate?: number | null;
	crit_dmg?: number | null;
	findings?: string[];
}

export interface Showcase {
	uid: string;
	player: { nickname: string; level: number; worldLevel: number; achievements: number };
	detailed: boolean;
	characters: ShowcaseChar[];
	preview: ShowcaseChar[];
	priorities: string[];
}

export interface NewsItem {
	title: string;
	url: string;
	snippet: string;
}

const UID_KEY = 'gc:uid';
const SID_KEY = 'gc:sid';

export const getUid = () =>
	(typeof localStorage === 'undefined' ? '' : localStorage.getItem(UID_KEY) || '702342940');
export const setUid = (v: string) => {
	try {
		localStorage.setItem(UID_KEY, v);
	} catch {
		/* private mode */
	}
};
export const EL_COLOR: Record<string, string> = {
	Fire: 'var(--pyro)',
	Water: 'var(--hydro)',
	Wind: 'var(--anemo)',
	Electric: 'var(--electro)',
	Grass: 'var(--dendro)',
	Ice: 'var(--cryo)',
	Rock: 'var(--geo)'
};

export const rarColor = (rarity: number) =>
	rarity >= 5 ? 'var(--rar5)' : 'var(--rar4)';

export const getSid = () => {
	try {
		return localStorage.getItem(SID_KEY);
	} catch {
		return null;
	}
};
export const setSid = (v: string | null) => {
	try {
		if (v) localStorage.setItem(SID_KEY, v);
		else localStorage.removeItem(SID_KEY);
	} catch {
		/* private mode */
	}
};

async function j<T>(r: Response): Promise<T> {
	if (!r.ok) {
		let detail = '';
		try {
			const b = (await r.json()) as { error?: unknown };
			if (b && typeof b.error === 'string' && b.error) detail = ` : ${b.error}`;
		} catch {
			/* corps illisible, on garde le statut seul */
		}
		throw new Error(`Erreur ${r.status}${detail}`);
	}
	return (await r.json()) as T;
}

export const fetchShowcase = (uid: string) =>
	fetch(`/api/showcase?uid=${encodeURIComponent(uid)}`).then(j<Showcase>);

export const fetchNews = (q: string, k = 5) =>
	fetch(`/api/news?q=${encodeURIComponent(q)}&k=${k}`).then(
		j<{ answer: string; results: NewsItem[] }>
	);

export const sendChat = (question: string, uid: string, session_id: string | null) =>
	fetch('/api/chat', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ question, uid, session_id })
	}).then(
		j<{
			answer: string;
			model: string;
			thinking: string;
			steps?: Step[];
			stats: { total_s: number | null; toks: number | null; out: number | null };
			session_id: string;
			detailed: boolean;
		}>
	);

export const sendChatStream = async (
	question: string,
	uid: string,
	session_id: string | null,
	onToken: (t: string) => void,
	onThinking?: (t: string) => void,
	onStep?: (s: Step) => void
): Promise<{
	answer: string;
	thinking: string;
	thinkSecs: number | null;
	stats: MsgStats;
	model: string;
	session_id: string;
	detailed: boolean;
	steps: Step[];
}> => {
	const r = await fetch('/api/chat/stream', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ question, uid, session_id })
	});
	if (!r.ok || !r.body) throw new Error(`Erreur ${r.status}`);
	const reader = r.body.getReader();
	const dec = new TextDecoder();
	let buf = '';
	let full = '';
	let thinking = '';
	let thinkSecs: number | null = null;
	const stats: MsgStats = {};
	let sid = session_id ?? '';
	let model = '';
	let detailed = false;
	const steps: Step[] = [];
	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		buf += dec.decode(value, { stream: true });
		let idx: number;
		while ((idx = buf.indexOf('\n\n')) >= 0) {
			const raw = buf.slice(0, idx);
			buf = buf.slice(idx + 2);
			for (const line of raw.split('\n')) {
				const t = line.trim();
				if (!t.startsWith('data:')) continue;
				const payload = t.slice(5).trim();
				if (!payload || payload === '[DONE]') continue;
				let ev: Record<string, unknown>;
				try {
					ev = JSON.parse(payload) as Record<string, unknown>;
				} catch {
					continue;
				}
				if (typeof ev['delta'] === 'string' && ev['delta']) {
					full += ev['delta'] as string;
					onToken(ev['delta'] as string);
				} else if (typeof ev['thinking'] === 'string' && ev['thinking']) {
					thinking += ev['thinking'] as string;
					onThinking?.(ev['thinking'] as string);
				} else if (ev['meta'] && typeof (ev['meta'] as Record<string, unknown>)['session_id'] === 'string') {
					sid = (ev['meta'] as Record<string, unknown>)['session_id'] as string;
				} else if (ev['step'] && typeof ev['step'] === 'object') {
					const s = ev['step'] as Step;
					steps.push(s);
					onStep?.(s);
				} else if (ev['tool'] && typeof ev['tool'] === 'object') {
					const s = ev['tool'] as Step;
					steps.push(s);
					onStep?.(s);
				} else if (ev['done']) {
					const d = ev['done'] as Record<string, unknown>;
					if (typeof d['session_id'] === 'string') sid = d['session_id'] as string;
					if (typeof d['model'] === 'string') model = d['model'] as string;
					detailed = d['detailed'] === true;
					if (Array.isArray(d['steps'])) {
						for (const s of d['steps'] as Step[]) {
							if (s && typeof s === 'object' && typeof (s as Step).tool === 'string') {
								if (!steps.some((x) => x.tool === (s as Step).tool && x.ms === (s as Step).ms)) {
									steps.push(s as Step);
								}
							}
						}
					}
					if (typeof d['thinking'] === 'string' && d['thinking']) thinking = d['thinking'] as string;
					if (typeof d['think_secs'] === 'number') thinkSecs = d['think_secs'] as number;
					const st = d['stats'] as Record<string, unknown> | undefined;
					if (st) {
						if (typeof st['total_s'] === 'number') stats.totalS = st['total_s'] as number;
						if (typeof st['toks'] === 'number') stats.toks = st['toks'] as number;
						if (typeof st['out'] === 'number') stats.out = st['out'] as number;
					}
				} else if (typeof ev['error'] === 'string') {
					throw new Error(ev['error'] as string);
				}
			}
		}
	}
	return { answer: full, thinking, thinkSecs, stats, model, session_id: sid, detailed, steps };
};

export const listSessions = (n = 20) =>
	fetch(`/api/sessions?n=${n}`).then(j<{ sessions: Session[] }>);

export const getMessages = (id: string) =>
	fetch(`/api/sessions/${id}/messages`).then(j<{ messages: StoredMsg[] }>);

export const deleteSession = (id: string) =>
	fetch(`/api/sessions/${id}`, { method: 'DELETE' }).then(j<{ ok: boolean }>);

export { renderMd } from './markdown';
