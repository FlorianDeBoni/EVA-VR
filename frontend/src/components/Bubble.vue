<template>
  <div class="message-bubble" :class="{ 'user-message': isUser, 'bot-message': !isUser }">
    <!-- Images -->
    <div v-if="images.length" class="image-list">
      <div
        v-for="image in images"
        :key="image.id"
        class="image-container"
      >
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
        <div v-if="image.title" class="image-caption">
          {{ image.title }}
        </div>
      </div>
    </div>

    <!-- Text -->
    <div class="message-content">
      {{ message }}
    </div>

    <div class="message-timestamp" v-if="timestamp">
      {{ timestamp }}
    </div>
  </div>
</template>

<script setup lang="ts">
interface ImagePayload {
  id: string;
  b64?: string;
  url?: string;
  title?: string;
  source?: string;
}

defineProps<{
  message: string;
  isUser?: boolean;
  timestamp?: string;
  images?: ImagePayload[];
}>();
</script>

<style scoped>
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  animation: slideIn 0.3s ease-out;
}

.user-message {
  align-self: flex-end;
}

.bot-message {
  align-self: flex-start;
}

.image-list {
  margin-bottom: 0.5rem;
}

.image-container {
  text-align: center;
  margin: 0.75rem 0;
}

.message-image {
  max-width: 300px;
  max-height: 300px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.image-caption {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
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

.message-timestamp {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}
</style>
