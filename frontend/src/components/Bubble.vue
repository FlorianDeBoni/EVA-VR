<template>
  <div class="message-bubble" :class="{ 'user-message': isUser, 'bot-message': !isUser }">
    <div class="message-content">
      <div v-html="processedMessage"></div>
    </div>
    <div class="message-timestamp" v-if="timestamp">
      {{ timestamp }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  message: string;
  isUser?: boolean;
  timestamp?: string;
  images?: { id: string, b64: string }[];
}

const props = withDefaults(defineProps<Props>(), {
  isUser: false,
  timestamp: '',
  images: () => []
});

// Replace [IMAGE_ID] with actual <img> tags or placeholder
const processedMessage = computed(() => {
  let result = props.message;

  // Find all [IMAGE_X] patterns
  const imagePattern = /\[IMAGE_(\d+)\]/g;
  const matches = [...result.matchAll(imagePattern)];

  matches.forEach(match => {
    const imageId = `IMAGE_${match[1]}`;
    const foundImage = props.images?.find(img => img.id === imageId);

    if (foundImage) {
      // Replace with actual image
      const imgTag = `<div class="image-container"><img src="data:image/png;base64,${foundImage.b64}" class="message-image" alt="Generated image" /></div>`;
      result = result.replace(match[0], imgTag);
    } else {
      // Replace with loading placeholder
      const placeholder = `<div class="image-placeholder"><div class="placeholder-icon">🖼️</div><div>Loading image...</div></div>`;
      result = result.replace(match[0], placeholder);
    }
  });

  // Convert newlines to <br> for proper formatting
  result = result.replace(/\n/g, '<br>');

  return result;
});
</script>

<style scoped>
.message-bubble {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-message {
  align-self: flex-end;
}

.bot-message {
  align-self: flex-start;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  word-wrap: break-word;
  font-size: 15px;
  line-height: 1.5;
}

.message-content :deep(.image-container) {
  text-align: center;
  margin: 1rem 0;
}

.message-content :deep(.message-image) {
  max-width: 300px;
  max-height: 300px;
  width: auto;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: block;
  margin: 0 auto;
}

.message-content :deep(.image-placeholder) {
  text-align: center;
  margin: 1rem 0;
  padding: 2rem;
  background: #f0f0f0;
  border-radius: 8px;
  color: #666;
}

.message-content :deep(.placeholder-icon) {
  font-size: 24px;
  margin-bottom: 0.5rem;
}

.message-content :deep(br) {
  display: block;
  content: "";
  margin: 0.25em 0;
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
  padding: 0 4px;
}

.user-message .message-timestamp {
  text-align: right;
}

.bot-message .message-timestamp {
  text-align: left;
}
</style>