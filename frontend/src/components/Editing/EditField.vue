<template>
  <textarea
    v-model="content"
    class="markdown-editor"
    placeholder="Edit markdown..."
    spellcheck="false"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const content = ref('')

onMounted(async () => {
  const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/getPrompt`, {
    method: "GET",
    credentials: "include",
  });
  const res_json = await res.json();
  content.value = res_json.prompt;
})

defineExpose({
  content
})
</script>

<style scoped>
.markdown-editor {
  width: 65vw;
  height: 75vh;
  resize: none;
  box-sizing: border-box;

  padding: 1rem;
  border: 1px solid #d0d0d0;
  border-radius: 8px;

  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
  line-height: 1.5;

  outline: none;
}

.markdown-editor:focus {
  border-color: #666;
}
</style>