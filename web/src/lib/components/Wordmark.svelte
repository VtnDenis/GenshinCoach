<script lang="ts">
	let { class: cls = '' }: { class?: string } = $props();
</script>

<span
	class="rc-wordmark font-display inline-flex items-baseline leading-none tracking-tight {cls}"
	aria-label="GenshinCoach"
>
	<span class="inline-block -skew-x-6">GENSHIN</span><span class="inline-block -skew-x-6 text-sport">COACH</span><span
		class="ml-0.5 inline-block size-[0.32em] -skew-x-6 self-start rounded-[1px] bg-sport"
		aria-hidden="true"
	></span>
</span>

<style>
	.rc-wordmark {
		font-kerning: none;
	}
</style>
