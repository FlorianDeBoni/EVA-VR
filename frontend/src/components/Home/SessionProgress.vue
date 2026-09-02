<template>
  <section class="step-indicator" aria-label="Session progress">
    <div class="step-indicator__heading">
      <span class="step-indicator__count">Step {{ safeStep }}/{{ steps.length }}</span>
      <span class="step-indicator__title">{{ currentTitle }}</span>
    </div>

    <div
      class="step-indicator__track"
      role="progressbar"
      :aria-valuenow="safeStep"
      aria-valuemin="1"
      :aria-valuemax="steps.length"
      :aria-valuetext="`Step ${safeStep} of ${steps.length}: ${currentTitle}`"
    >
      <span
        v-for="stepNumber in steps.length"
        :key="stepNumber"
        class="step-indicator__segment"
        :class="{ 'step-indicator__segment--complete': stepNumber <= safeStep }"
      />
    </div>

    <p class="step-indicator__next">
      {{ nextTitle ? `Next: ${nextTitle}` : 'Final step' }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  currentStep: number;
}>();

const steps = [
  'Discover your context',
  'Generate directions',
  'Evaluate concepts',
  'Synthesize the vision',
  'Compose and share'
];

const safeStep = computed(() => Math.min(Math.max(props.currentStep, 1), steps.length));
const currentTitle = computed(() => steps[safeStep.value - 1]);
const nextTitle = computed(() => steps[safeStep.value] ?? '');
</script>

<style scoped>
.step-indicator {
  width: clamp(280px, 38vw, 520px);
  color: #ffffff;
}

.step-indicator__heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.step-indicator__count {
  flex-shrink: 0;
  color: #aeb8ff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.step-indicator__title {
  overflow: hidden;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-indicator__track {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 3px;
  margin-top: 5px;
}

.step-indicator__segment {
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
}

.step-indicator__segment--complete {
  background: #7d8cff;
}

.step-indicator__next {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 11px;
}

@media (max-width: 780px) {
  .step-indicator {
    order: 3;
    width: 100%;
  }
}
</style>
