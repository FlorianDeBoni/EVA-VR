<template>
  <div class="chat-input-container">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="message"
        @input="adjustHeight"
        @keydown="handleEnter"
        :disabled="disabled"
        placeholder="Type your message... (ctrl+Enter for new lines)"
        rows="1"
        class="chat-input"
      ></textarea>
      <button 
        @click="handleSend"
        :disabled="!message.trim() || disabled"
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

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue';

interface Props {
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
});

const emit = defineEmits<{
  send: [message: string]
}>();

const message = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const maxLines = 4;
const lineHeight = 24;

onMounted(() => {
  nextTick(() => {
    textareaRef.value?.focus();
  });

  watch(
  () => props.disabled,
  (isDisabled) => {
    if (!isDisabled) {
      nextTick(() => {
        textareaRef.value?.focus();
      });
    }
  }
);

});

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
    textarea.scrollTop = textarea.scrollHeight;
  });
};


const handleEnter = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return;
  if (props.disabled) return;

  const textarea = textareaRef.value;
  if (!textarea) return;

  // Ctrl / Cmd + Enter → insert newline manually
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault();

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;

    message.value =
      message.value.slice(0, start) +
      '\n' +
      message.value.slice(end);

    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = start + 1;
      adjustHeight();
    });

    return;
  }

  // Enter → send
  event.preventDefault();
  handleSend();
};


const handleSend = () => {
  if (message.value.trim() && !props.disabled) {
    emit('send', message.value);
    message.value = '';
    
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = 'auto';
      }
    });
  }
};
</script>

<style scoped>
.chat-input-container {
  width: 100%;
  padding: 16px;
  background: #ffffff;
  border-top: 1px solid #e5e7eb;
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
  max-height: 96px;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
  padding: 0;
  margin: 0;
  align-self: center;
}

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