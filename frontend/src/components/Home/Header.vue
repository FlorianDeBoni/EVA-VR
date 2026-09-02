<template>
  <header class="banner">
    <span class="project-name">EVA-VR ChatBot</span>
    <div class="session-controls">
      <SessionProgress :currentStep="currentStep" />
    </div>
    <RestartButton @restart="$emit('restart')" :isStreaming="isStreaming" />
    <span class="version">Last updated: 2nd September 2026</span>
  </header>
</template>

<script setup lang="ts">
import RestartButton from './RestartButton.vue';
import SessionProgress from './SessionProgress.vue';

const emit = defineEmits(['restart'])

defineProps<{
  isStreaming: boolean;
  currentStep: number;
}>();
</script>

<style scoped>
.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  min-height: 68px;
  background: #1a1a2e;
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
}

.session-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  min-width: 0;
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

@media (max-width: 780px) {
  .banner {
    flex-wrap: wrap;
    gap: 10px 16px;
    height: auto;
    padding: 12px 16px;
  }

  .session-controls {
    order: 3;
    width: 100%;
    justify-content: space-between;
  }

  .version {
    margin-left: auto;
  }
}

@media (max-width: 520px) {
  .session-controls {
    flex-wrap: wrap;
  }
}
</style>
