<template>
  <button
    class="restart-btn"
    :class="{ 'is-animating': animating }"
    @click="handleClick"
    :disabled="animating || isStreaming"
    aria-label="Restart Chat"
  >
    <svg
      class="restart-btn__icon"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M5 12A7 7 0 1 1 12 19"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
      />
      <path
        d="M5 7v5h5"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <span class="restart-btn__label">{{ animating ? 'Restarting' : 'Restart chat' }}</span>
  </button>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['restart'])
const animating = ref(false)

function handleClick() {
  if (animating.value) return
  animating.value = true
  emit('restart')
  setTimeout(() => {
    animating.value = false
  }, 750)
}

const props = defineProps({
  isStreaming: { type: Boolean, default: false }
})
</script>

<style scoped>
.restart-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 0.01em;
  transition: color 0.18s ease, border-color 0.18s ease;
  outline: none;
}

.restart-btn:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.6);
}

.restart-btn:focus-visible {
  border-color: #fff;
  color: #fff;
}

.restart-btn:disabled {
  cursor: not-allowed;
  color: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.1);
}

.restart-btn__icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  transition: color 0.18s ease;
}

.restart-btn.is-animating .restart-btn__icon {
  animation: spin 0.65s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(-360deg); }
}

.restart-btn__label {
  line-height: 1;
}
</style>