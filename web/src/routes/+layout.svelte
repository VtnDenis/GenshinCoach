<script lang="ts">
	import './layout.css';
	import '@fontsource/anton';
	import '@fontsource-variable/jetbrains-mono';

	let { children } = $props();
</script>

<div class="rc-grain" aria-hidden="true"></div>
{@render children()}
