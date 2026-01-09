<template>
  <div class="chat-input-container">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="message"
        @input="adjustHeight"
        @keydown.enter="handleEnter"
        placeholder="Type your message... (Shift+Enter to send)"
        rows="1"
        class="chat-input"
      ></textarea>
      <button 
        @click="handleSend"
        :disabled="!message.trim()"
        class="send-button"
        aria-label="Send message"
      >
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="2" 
          stroke-linecap="round" 
          stroke-linejoin="round"
          class="send-icon"
        >
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, nextTick } from 'vue';

export default defineComponent({
  name: 'ChatInput',
  emits: ['send'],
  setup(props, { emit }) {
    const message = ref('');
    const textareaRef = ref<HTMLTextAreaElement | null>(null);
    const maxLines = 4;
    const lineHeight = 24; // Adjust based on your font size

    const adjustHeight = () => {
      nextTick(() => {
        if (!textareaRef.value) return;
        
        const textarea = textareaRef.value;
        textarea.style.height = 'auto';
        
        const scrollHeight = textarea.scrollHeight;
        const maxHeight = lineHeight * maxLines;
        
        if (scrollHeight > maxHeight) {
          textarea.style.height = `${maxHeight}px`;
          textarea.style.overflowY = 'auto';
        } else {
          textarea.style.height = `${scrollHeight}px`;
          textarea.style.overflowY = 'hidden';
        }
      });
    };

    const handleEnter = (event: KeyboardEvent) => {
      // Shift+Enter sends the message
      if (event.shiftKey) {
        event.preventDefault();
        handleSend();
      }
      // Regular Enter just adds a new line (default behavior)
    };

    const handleSend = () => {
      if (message.value.trim()) {
        emit('send', message.value);
        message.value = '';
        
        // Reset textarea height
        nextTick(() => {
          if (textareaRef.value) {
            textareaRef.value.style.height = 'auto';
          }
        });
      }
    };

    return {
      message,
      textareaRef,
      adjustHeight,
      handleEnter,
      handleSend
    };
  }
});
</script>

<style scoped>
.chat-input-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  width: 100%;
  padding: 16px;
  background: #ffffff;
  border-top: 1px solid #e5e7eb;
  z-index: 100;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  max-width: 800px;
  margin: 0 auto;
  padding: 12px 16px;
  background: #f9fafb;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  transition: border-color 0.2s;
  min-height: 48px;
}

.input-wrapper:focus-within {
  border-color: #3b82f6;
  background: #ffffff;
}

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  line-height: 24px;
  resize: none;
  font-family: inherit;
  color: #111827;
  min-height: 24px;
  max-height: 96px; /* 4 lines * 24px */
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
  padding: 0;
  margin: 0;
  align-self: center;
}

/* Webkit browsers (Chrome, Safari, Edge) */
.chat-input::-webkit-scrollbar {
  width: 8px;
}

.chat-input::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.chat-input::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.chat-input::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
  border: 2px solid transparent;
  background-clip: padding-box;
}

.chat-input::placeholder {
  color: #9ca3af;
}

.send-button {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  align-self: flex-end;
  margin-bottom: 0;
}

.send-button:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
}

.send-button:active:not(:disabled) {
  transform: translateY(0);
}

.send-button:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

.send-icon {
  width: 20px;
  height: 20px;
}
</style>