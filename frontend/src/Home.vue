<template>
  <div class="chat-app">
    <ChatHistory>
      <div v-if="messages.length === 0" class="welcome-message">
        Welcome to EVA-VR chatBot, please start a conversation...
      </div>

      <MessageBubble
        v-for="(msg, index) in messages"
        :key="index"
        :message="msg.text"
        :isUser="msg.isUser"
        :timestamp="msg.timestamp"
        :images="msg.images"
      />
    </ChatHistory>

    <ChatInput @send="handleSend" :disabled="isStreaming" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import ChatHistory from './components/ChatHistory.vue';
import MessageBubble from './components/Bubble.vue';
import ChatInput from './components/InputMessage.vue';

interface ImagePayload {
  id: string;
  b64?: string;
  url?: string;
  title?: string;
  source?: string;
}

interface Message {
  text: string;
  isUser: boolean;
  timestamp: string;
  images: ImagePayload[];
}

const messages = ref<Message[]>([{
  text: "👋 Hello, and welcome to DOKK1 2045! Would you like to continue in English or Danish?",
  isUser: false,
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  images: []
}]);

const currentImageB64 = ref<string | null>(null);

const isStreaming = ref(false);
let abortController: AbortController | null = null;

const getConversationHistory = () =>
  messages.value.map(msg => ({
    role: msg.isUser ? 'user' : 'assistant',
    content: msg.text
  }));

const handleSend = async (messageText: string) => {
  messages.value.push({
    text: messageText,
    isUser: true,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    images: []
  });

  const botMessageIndex = messages.value.length;

  messages.value.push({
    text: '',
    isUser: false,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    images: []
  });

  isStreaming.value = true;

  if (abortController) abortController.abort();
  abortController = new AbortController();

  try {
    const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: messageText,
        history: getConversationHistory(),
        reference_image: currentImageB64.value ?? ""
      }),
      signal: abortController.signal
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    if (!reader) throw new Error('No response body');

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;

        const data = line.startsWith('data: ')
          ? line.substring(6)
          : line;

        if (data === '[DONE]') {
          isStreaming.value = false;
          abortController = null;
          continue;
        }

        const parsed = JSON.parse(data);

        if (parsed.type === 'image') {
          messages.value[botMessageIndex].images.push({
            id: parsed.id,
            b64: parsed.b64,
            url: parsed.url,
            title: parsed.title,
            source: parsed.source
          });

          if (parsed.b64) {
            currentImageB64.value = parsed.b64;
          }
        }


        if (parsed.type === 'text' && parsed.delta) {
          messages.value[botMessageIndex].text += parsed.delta;
        }
      }
    }
  } catch (err) {
    messages.value[botMessageIndex].text =
      'Sorry, something went wrong while processing your request.';
  } finally {
    isStreaming.value = false;
    abortController = null;
  }
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

.welcome-message {
  color: #9ca3af;
  font-size: 16px;
  text-align: center;
  padding: 20px;
}
</style>