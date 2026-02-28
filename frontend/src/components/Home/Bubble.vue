<template>
  <div class="message-bubble" :class="{ 'user-message': isUser, 'bot-message': !isUser }">
    <!-- Images -->
    <div v-if="images && images.length" class="image-list">
      <div v-for="image in images" :key="image.id" class="image-container">
        <img
          v-if="image.b64"
          :src="`data:image/png;base64,${image.b64}`"
          class="message-image"
          :alt="image.title || 'Generated image'"
        />
        <img
          v-else-if="image.url"
          :src="image.url"
          class="message-image"
          :alt="image.title || 'Reference image'"
        />
        <div v-if="image.title" class="image-caption">{{ image.title }}</div>
      </div>
    </div>

    <!-- Text -->
    <div v-if="message.length > 0" class="message-body">
      <div class="message-content">
        <div class="message-text" v-html="renderedMessage" />
        <div class="message-footer">
          <div class="message-timestamp" v-if="timestamp">{{ timestamp }}</div>
        </div>
      </div>

      <div
        v-if="displayedFeedback"
        class="feedback-wrapper"
        :class="{ 'feedback-wrapper--disabled': isStreaming }"
      >
        <Feedback @feedback="onFeedback" :isStreaming="isStreaming" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import Feedback from './Feedback.vue'

interface ImagePayload {
  id: string
  b64?: string
  url?: string
  title?: string
  source?: string
}

const props = defineProps<{
  message: string
  isUser?: boolean
  timestamp?: string
  images?: ImagePayload[]
  isStreaming?: boolean
  displayedFeedback?: boolean
}>()

const emit = defineEmits<{
  (e: 'feedback', payload: { rating: 'up' | 'down'; note: string }): void
}>()

const justSubmitted = ref(false)

function onFeedback(payload: { rating: 'up' | 'down'; note: string }) {
  emit('feedback', payload)
  justSubmitted.value = true
}

const renderedMessage = computed(() =>
  marked(props.message, { breaks: true, gfm: true })
)
</script>

<style scoped>
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  animation: slideIn 0.3s ease-out;
  overflow: visible;
}

.user-message { align-self: flex-end; }
.bot-message  { align-self: flex-start; }

.image-list { margin-bottom: 0.5rem; }

.image-container { text-align: center; margin: 0.75rem 0; }

.message-image {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.image-caption { font-size: 12px; color: #6b7280; margin-top: 4px; }

.message-body {
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.message-content {
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.5;
  overflow: visible;
}

.user-message .message-content {
  background: #3b82f6;
  color: white;
  border-bottom-right-radius: 4px;
}

.bot-message .message-content {
  background: #f3f4f6;
  color: #111827;
  border-bottom-left-radius: 4px;
}

/* ── Markdown prose ── */
.message-text {
  text-align: justify;
  hyphens: auto;
}

.message-text :deep(p) { margin: 0 0 0.5em; }
.message-text :deep(p:last-child) { margin-bottom: 0; }

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4) {
  font-weight: 600;
  margin: 0.75em 0 0.25em;
  line-height: 1.3;
}
.message-text :deep(h1) { font-size: 1.2em; }
.message-text :deep(h2) { font-size: 1.1em; }
.message-text :deep(h3) { font-size: 1.0em; }

.message-text :deep(ul),
.message-text :deep(ol) {
  padding-left: 1.4em;
  margin: 0.4em 0;
}
.message-text :deep(li) { margin: 0.2em 0; }

.message-text :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85em;
  padding: 1px 5px;
  border-radius: 4px;
}
.user-message .message-text :deep(code) { background: rgba(255,255,255,0.2); }
.bot-message  .message-text :deep(code) { background: #e5e7eb; color: #1f2937; }

.message-text :deep(pre) {
  border-radius: 8px;
  padding: 10px 14px;
  overflow-x: auto;
  margin: 0.5em 0;
  font-size: 0.85em;
  line-height: 1.6;
}
.user-message .message-text :deep(pre) { background: rgba(255,255,255,0.15); }
.bot-message  .message-text :deep(pre) { background: #e5e7eb; }
.message-text :deep(pre code) { background: none; padding: 0; }

.message-text :deep(blockquote) {
  margin: 0.5em 0;
  padding-left: 0.75em;
  border-left: 3px solid currentColor;
  opacity: 0.75;
}

.message-text :deep(a) { text-decoration: underline; text-underline-offset: 2px; }
.user-message .message-text :deep(a) { color: #bfdbfe; }
.bot-message  .message-text :deep(a) { color: #2563eb; }

.message-text :deep(strong) { font-weight: 600; }
.message-text :deep(em)     { font-style: italic; }

.message-text :deep(hr) {
  border: none;
  border-top: 1px solid currentColor;
  opacity: 0.2;
  margin: 0.75em 0;
}

/* ── Footer ── */
.message-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  min-height: 18px;
}

.message-timestamp {
  font-size: 11px;
  flex-shrink: 0;
}
.user-message .message-timestamp { color: rgba(255,255,255,0.65); }
.bot-message  .message-timestamp { color: #9ca3af; }

/* ── Feedback wrapper ── */
.feedback-wrapper { transition: opacity 0.2s ease; }
.feedback-wrapper--disabled {
  opacity: 0.4;
  pointer-events: none;
  filter: grayscale(1);
  cursor: not-allowed;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>