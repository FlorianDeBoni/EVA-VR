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
      <div class="message-content">{{ message }}</div>

      <div class="message-footer">
        <div class="message-timestamp" v-if="timestamp">{{ timestamp }}</div>
        <Feedback @feedback="emit('feedback', $event)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import Feedback from './Feedback.vue'

interface ImagePayload {
  id: string
  b64?: string
  url?: string
  title?: string
  source?: string
}

defineProps<{
  message: string
  isUser?: boolean
  timestamp?: string
  images?: ImagePayload[]
}>()

const emit = defineEmits<{
  (e: 'feedback', payload: { rating: 'up' | 'down'; note: string }): void
}>()
</script>

<style scoped>
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  animation: slideIn 0.3s ease-out;
  /* Let the absolutely-positioned popover escape the bubble bounds */
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
  /* Same: don't clip the popover */
  overflow: visible;
}

.message-content {
  white-space: pre-wrap;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.5;
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

.message-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* Fixed height keeps timestamp and feedback buttons vertically stable */
  min-height: 28px;
  margin-top: 4px;
  /* Allow the popover to overflow downward without disrupting layout */
  overflow: visible;
  position: relative;
}

.message-timestamp {
  font-size: 11px;
  color: #9ca3af;
  /* Prevent timestamp from being pushed around when feedback badge appears */
  flex-shrink: 0;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>