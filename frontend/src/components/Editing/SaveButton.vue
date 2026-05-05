<template>
  <button class="save-btn" @click="emit('save')" :class="{ saving: isSaving }" @mousedown="press" @mouseup="release" @mouseleave="release">
    <span class="save-btn__track">
      <span class="save-btn__icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
          <polyline points="17 21 17 13 7 13 7 21"/>
          <polyline points="7 3 7 8 15 8"/>
        </svg>
      </span>
      <span class="save-btn__label">Save</span>
    </span>
    <span class="save-btn__shimmer" />
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ save: [] }>()

const isSaving = ref(false)
const pressed = ref(false)

function press() {
  pressed.value = true
}

function release() {
  pressed.value = false
}
</script>

<style scoped>
.save-btn {
  --ink: #0f172a;
  --paper: #f8fafc;
  --accent: #2563eb;
  --accent-dark: #1d4ed8;
  --radius: 10px;
  --font: 'DM Sans', 'Segoe UI', sans-serif;

  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  border-radius: var(--radius);
  background: var(--accent);
  cursor: pointer;
  outline: none;
  overflow: hidden;
  box-shadow:
    0 1px 0 0 var(--accent-dark) inset,
    0 4px 12px -2px rgba(37, 99, 235, 0.45),
    0 2px 4px -1px rgba(37, 99, 235, 0.2);
  transition:
    transform 90ms ease,
    box-shadow 90ms ease,
    background 150ms ease;
  font-family: var(--font);
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.save-btn:hover {
  background: #2d6ef5;
  box-shadow:
    0 1px 0 0 var(--accent-dark) inset,
    0 6px 18px -2px rgba(37, 99, 235, 0.5),
    0 3px 6px -1px rgba(37, 99, 235, 0.25);
  transform: translateY(-1px);
}

.save-btn:active {
  transform: translateY(1px) scale(0.98);
  box-shadow:
    0 1px 0 0 var(--accent-dark) inset,
    0 2px 6px -1px rgba(37, 99, 235, 0.3);
}

.save-btn:focus-visible {
  outline: 3px solid rgba(37, 99, 235, 0.4);
  outline-offset: 3px;
}

.save-btn__track {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px 10px 16px;
  position: relative;
  z-index: 1;
}

.save-btn__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: #fff;
  opacity: 0.92;
  transition: transform 150ms ease;
}

.save-btn:hover .save-btn__icon {
  transform: scale(1.08);
}

.save-btn__icon svg {
  width: 100%;
  height: 100%;
}

.save-btn__label {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #fff;
  line-height: 1;
}

/* Shimmer sweep */
.save-btn__shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    transparent 40%,
    rgba(255, 255, 255, 0.18) 50%,
    transparent 60%
  );
  background-size: 200% 100%;
  background-position: 200% 0;
  border-radius: inherit;
  pointer-events: none;
  transition: none;
}

.save-btn:hover .save-btn__shimmer {
  animation: shimmer 600ms ease forwards;
}

@keyframes shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -50% 0; }
}
</style>