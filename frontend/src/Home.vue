<script setup lang="ts">
import { ref, computed } from 'vue';

const text = ref('');
const images = ref<{ id: string, b64: string }[]>([]);
let eventSource: EventSource | null = null;

const handlePress = () => {
  text.value = '';
  images.value = [];

  if (eventSource) eventSource.close();

  eventSource = new EventSource(`${import.meta.env.VITE_BACKEND_URL}/api/check`);

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      eventSource?.close();
      eventSource = null;
      return;
    }

    const data = JSON.parse(event.data);

    if (data.type === 'image') {
      images.value.push({ id: data.id, b64: data.b64 });
      return;
    }

    if (data.type === 'text' && data.delta !== "[DONE]") {
      text.value += data.delta;
      return;
    }
  };

  eventSource.onerror = (err) => {
    console.error('SSE error', err);
    eventSource?.close();
    eventSource = null;
  };
};

// Replace [IMAGE_1] with <img> tags
const processedText = computed(() => {
  let result = text.value;

  images.value.forEach(img => {
    const imgTag = `<div style="text-align:center; margin:1rem 0;">
                      <img src="data:image/png;base64,${img.b64}" style="max-width:300px;" />
                    </div>`;
    result = result.replace(`[${img.id}]`, imgTag);
  });

  return result;
});
</script>

<template>
  <button @click="handlePress">TEST</button>

  <div style="white-space: pre-wrap; margin-top: 1rem;">
    <span v-html="processedText"></span>
  </div>
</template>
