<script setup lang="ts">
import Test from "./components/Test.vue"
import { ref } from 'vue';

const text = ref('');
let eventSource: EventSource | null = null;

const handlePress = () => {
  text.value = '';
  
  // Close previous stream if any
  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource(`${import.meta.env.VITE_BACKEND_URL}/api/check`);

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      eventSource?.close();
      eventSource = null;
      return;
    }

    text.value += event.data;
  };

  eventSource.onerror = (err) => {
    console.error('SSE error', err);
    eventSource?.close();
    eventSource = null;
  };
};
</script>

<template>
  <Test></Test>
  <button @click="handlePress">TEST</button>

  <div style="white-space: pre-wrap; margin-top: 1rem;">
    {{ text }}
  </div>
</template>
