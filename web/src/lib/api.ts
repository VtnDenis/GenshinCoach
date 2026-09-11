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
}

export interface Step {
	tool: string;
	ms?: number | null;
	result?: string;
	error?: string;
}

export interface Msg {
	role: 'user' | 'assistant';
	text: string;
	model?: string | null;
}

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
	}).then(j<{ answer: string; model: string; session_id: string; detailed: boolean }>);

export const sendChatStream = async (
	question: string,
	uid: string,
	session_id: string | null,
	onToken: (t: string) => void
): Promise<{ answer: string; model: string; session_id: string; detailed: boolean }> => {
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
	let sid = session_id ?? '';
	let model = '';
	let detailed = false;
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
				} else if (ev['meta'] && typeof (ev['meta'] as Record<string, unknown>)['session_id'] === 'string') {
					sid = (ev['meta'] as Record<string, unknown>)['session_id'] as string;
				} else if (ev['done']) {
					const d = ev['done'] as Record<string, unknown>;
					if (typeof d['session_id'] === 'string') sid = d['session_id'] as string;
					if (typeof d['model'] === 'string') model = d['model'] as string;
					detailed = d['detailed'] === true;
				} else if (typeof ev['error'] === 'string') {
					throw new Error(ev['error'] as string);
				}
			}
		}
	}
	return { answer: full, model, session_id: sid, detailed };
};

export const listSessions = (n = 20) =>
	fetch(`/api/sessions?n=${n}`).then(j<{ sessions: Session[] }>);

export const getMessages = (id: string) =>
	fetch(`/api/sessions/${id}/messages`).then(j<{ messages: StoredMsg[] }>);

export const deleteSession = (id: string) =>
	fetch(`/api/sessions/${id}`, { method: 'DELETE' }).then(j<{ ok: boolean }>);

export { renderMd } from './markdown';
