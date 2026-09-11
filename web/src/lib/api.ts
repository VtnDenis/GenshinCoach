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
	if (!r.ok) throw new Error(`Erreur ${r.status}`);
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

export const listSessions = (n = 20) =>
	fetch(`/api/sessions?n=${n}`).then(j<{ sessions: Session[] }>);

export const getMessages = (id: string) =>
	fetch(`/api/sessions/${id}/messages`).then(j<{ messages: StoredMsg[] }>);

export const deleteSession = (id: string) =>
	fetch(`/api/sessions/${id}`, { method: 'DELETE' }).then(j<{ ok: boolean }>);

export { renderMd } from './markdown';
