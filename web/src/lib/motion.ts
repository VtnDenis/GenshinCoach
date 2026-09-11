// Tiny motion.dev-inspired helpers, no dep, SSR-safe.
// rise: WAAPI enter (y+fade, spring-ish easing). inView: reveal once on scroll.

export function prefersReduced(): boolean {
	try {
		return matchMedia('(prefers-reduced-motion: reduce)').matches;
	} catch {
		return false;
	}
}

export function rise(node: HTMLElement, opts?: { delay?: number; y?: number }) {
	if (typeof window === 'undefined' || prefersReduced()) return;
	const delay = opts?.delay ?? 0;
	const y = opts?.y ?? 8;
	try {
		node.animate(
			[
				{ opacity: 0, transform: `translateY(${y}px)` },
				{ opacity: 1, transform: 'translateY(0)' }
			],
			{ duration: 320, delay, easing: 'cubic-bezier(0.23,1,0.32,1)', fill: 'backwards' }
		);
	} catch {
		/* WAAPI unavailable, CSS fallback handles it */
	}
}

export function inView(node: HTMLElement, opts?: { delay?: number }) {
	if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
		rise(node, opts);
		return;
	}
	if (prefersReduced()) return;
	node.style.opacity = '0';
	const io = new IntersectionObserver(
		(es) => {
			if (es[0]?.isIntersecting) {
				node.style.opacity = '';
				rise(node, opts);
				io.disconnect();
			}
		},
		{ rootMargin: '40px' }
	);
	io.observe(node);
	return {
		destroy() {
			io.disconnect();
		}
	};
}
