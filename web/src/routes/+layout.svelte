<script lang="ts">
	import './layout.css';
	import '@fontsource/baloo-2/600.css';
	import '@fontsource/baloo-2/700.css';
	import '@fontsource-variable/jetbrains-mono';

	let { children } = $props();
</script>

<div class="rc-grain" aria-hidden="true"></div>
{@render children()}
