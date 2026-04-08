<template>
  <header class="banner">
    <span class="project-name">EVA-VR ChatBot</span>
    <RestartButton @restart="$emit('restart')" :isStreaming="isStreaming" />
    <span class="version">Last updated: 8th April 2026</span>
  </header>
</template>

<script setup lang="ts">
import RestartButton from './RestartButton.vue';

const emit = defineEmits(['restart'])

defineProps<{
  isStreaming: boolean;
}>();
</script>

<style scoped>
.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 52px;
  background: #1a1a2e;
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
}

.project-name {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.version {
  font-size: 13px;
  color: #9ca3af;
  background: #2a2a3e;
  padding: 3px 10px;
  border-radius: 12px;
}
</style>