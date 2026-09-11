<script lang="ts">
	import { page } from '$app/state';
	import Chat from '../../+page.svelte';
</script>

<Chat initialSid={page.params.id} />
