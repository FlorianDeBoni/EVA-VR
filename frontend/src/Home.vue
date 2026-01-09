<template>
  <div class="chat-app">
    <div class="chat-content">
      <ChatHistory>
        <MessageBubble
          v-for="(msg, index) in messages"
          :key="index"
          :message="msg.text"
          :isUser="msg.isUser"
          :timestamp="msg.timestamp"
          :images="msg.images"
        />
      </ChatHistory>
    </div>
    
    <ChatInput @send="handleSend" :disabled="isStreaming" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import ChatHistory from './components/ChatHistory.vue';
import MessageBubble from './components/Bubble.vue';
import ChatInput from './components/InputMessage.vue';

interface Message {
  text: string;
  isUser: boolean;
  timestamp: string;
  images?: { id: string, b64: string }[];
}

const messages = ref<Message[]>([
  {
    text: 'Hello! How can I help you today?',
    isUser: false,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
]);

const isStreaming = ref(false);
let eventSource: EventSource | null = null;

const handleSend = (messageText: string) => {
  // Add user message
  messages.value.push({
    text: messageText,
    isUser: true,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  });

  // Create a placeholder for the bot response
  const botMessageIndex = messages.value.length;
  messages.value.push({
    text: '',
    isUser: false,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    images: []
  });

  isStreaming.value = true;

  // Close any existing connection
  if (eventSource) eventSource.close();

  // Start SSE connection
  eventSource = new EventSource(`${import.meta.env.VITE_BACKEND_URL}/api/check`);

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      eventSource?.close();
      eventSource = null;
      isStreaming.value = false;
      return;
    }

    const data = JSON.parse(event.data);

    if (data.type === 'image') {
      messages.value[botMessageIndex].images?.push({ 
        id: data.id, 
        b64: data.b64 
      });
      return;
    }

    if (data.type === 'text' && data.delta !== "[DONE]") {
      messages.value[botMessageIndex].text += data.delta;
      return;
    }
  };

  eventSource.onerror = (err) => {
    console.error('SSE error', err);
    eventSource?.close();
    eventSource = null;
    isStreaming.value = false;
    
    // Optionally add an error message
    messages.value[botMessageIndex].text = 'Sorry, there was an error processing your request.';
  };
};
</script>

<style scoped>
.chat-app {
  width: 100%;
  height: 100vh;
  display: grid;
  grid-template-rows: 1fr auto;
  overflow: hidden;
}

.chat-content {
  overflow: hidden;
  position: relative;
}
</style>