<template>
  <div class="chat-input-container">
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="message"
        @input="adjustHeight"
        @keydown="handleEnter"
        :disabled="disabled"
        placeholder="Type your message... (Enter to send, Ctrl+Enter for newline)"
        rows="1"
        class="chat-input"
      ></textarea>
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
  send: [message: string];
}>();

const message = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const maxLines = 4;
const lineHeight = 24;

onMounted(() => {
  nextTick(() => {
    textareaRef.value?.focus();
  });
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

const adjustHeight = () => {
  nextTick(() => {
    const textarea = textareaRef.value;
    if (!textarea) return;

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

const insertNewline = () => {
  const textarea = textareaRef.value;
  if (!textarea) return;

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
};

const handleEnter = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return;
  if (props.disabled) return;

  event.preventDefault();

  if (event.ctrlKey || event.metaKey) {
    insertNewline();
    return;
  }

  handleSend();
};

const handleSend = () => {
  if (!message.value.trim() || props.disabled) return;

  emit('send', message.value);
  message.value = '';

  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
      textareaRef.value.style.overflowY = 'hidden';
      textareaRef.value.focus();
    }
  });
};
</script>

<style scoped>
.chat-input-container {
  width: 100%;
}

.input-wrapper {
  width: 100%;

  display: flex;
  align-items: flex-end;
  gap: 12px;

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
  width: 100%;
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

.chat-input:disabled {
  cursor: not-allowed;
  color: #6b7280;
}
</style>