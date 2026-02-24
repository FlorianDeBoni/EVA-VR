<template>
  <div class="prose" v-html="renderedPrompt"></div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { marked } from 'marked';

const prompt = ref("")
const renderedPrompt = computed(() => marked(prompt.value))

onMounted(async () => {
  const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/getPrompt`, {
    method: "GET",
    credentials: "include",
  });
  const res_json = await res.json();
  prompt.value = res_json.prompt;
});
</script>

<style>
/* NOT scoped — targets the whole page */
*, *::before, *::after {
  box-sizing: border-box;
}

body, html {
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  max-width: 100vw;
}
</style>

<style scoped>
.prose {
  max-width: 860px;
  width: 100%;
  margin: 40px auto;
  padding: 0 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.7;
  color: #1a1a1a;
}

.prose :deep(table) {
  border-collapse: collapse;
  width: 100%;
  display: block;
  overflow-x: auto;
}

.prose :deep(h1), .prose :deep(h2), .prose :deep(h3) {
  color: #111;
  margin-top: 1.5em;
}

.prose :deep(pre) {
  background: #f4f4f4;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  white-space: pre-wrap;   /* ← wraps long code lines instead of overflowing */
  word-break: break-all;
}

.prose :deep(code) {
  background: #f4f4f4;
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 0.9em;
  word-break: break-all;   /* ← breaks long inline code */
}

.prose :deep(th), .prose :deep(td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
}

.prose :deep(th) {
  background: #f0f0f0;
}
</style>