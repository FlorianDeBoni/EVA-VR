<template>
  <div class="chat-app">
    <div class="chat-content">
      <ChatHistory>
        <!-- Welcome message when no messages -->
        <div v-if="messages.length === 0" class="welcome-message">
          Welcome to EVA-VR chatBot, please start a conversation...
        </div>

        <!-- Message bubbles -->
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

const messages = ref<Message[]>([]);

const isStreaming = ref(false);
let abortController: AbortController | null = null;

// Convert messages to history format for the backend
const getConversationHistory = () => {
  return messages.value.map(msg => ({
    role: msg.isUser ? 'user' : 'assistant',
    content: msg.text
  }));
};

const handleSend = async (messageText: string) => {
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

  // Cancel any existing request
  if (abortController) abortController.abort();
  abortController = new AbortController();

  try {
    const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: messageText,
        history: getConversationHistory()
      }),
      signal: abortController.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('No response body');
    }

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      
      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;

        let data = line;
        
        // Remove 'data: ' prefix if present
        if (line.startsWith('data: ')) {
          data = line.substring(6);
        }

        if (data === '[DONE]') {
          isStreaming.value = false;
          abortController = null;
          continue;
        }

        try {
          const parsed = JSON.parse(data);

          if (parsed.type === 'image') {
            messages.value[botMessageIndex].images?.push({
              id: parsed.id,
              b64: parsed.b64
            });
          } else if (parsed.type === 'text' && parsed.delta && parsed.delta !== '[DONE]') {
            messages.value[botMessageIndex].text += parsed.delta;
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e, 'Line:', data);
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Request was aborted');
    } else {
      console.error('Fetch error:', error);
      messages.value[botMessageIndex].text = 'Sorry, there was an error processing your request.';
    }
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

.chat-content {
  overflow: hidden;
  position: relative;
}

.welcome-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-size: 16px;
  text-align: center;
  padding: 20px;
}
</style>