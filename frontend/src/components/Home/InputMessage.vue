<template>
  <div class="chat-input-container">
    <div class="input-wrapper" :class="{ 'input-wrapper--listening': isListening }">
      <textarea
        ref="textareaRef"
        v-model="message"
        @input="adjustHeight"
        @keydown="handleEnter"
        :disabled="disabled"
        :placeholder="isListening ? 'Listening… Speak now' : 'Type or use the microphone…'"
        rows="1"
        class="chat-input"
      ></textarea>
      <button
        v-if="speechRecognitionSupported"
        type="button"
        class="microphone-button"
        :class="{ 'microphone-button--listening': isListening }"
        :disabled="disabled"
        :aria-label="isListening ? 'Stop voice input' : 'Start voice input'"
        :aria-pressed="isListening"
        :title="isListening ? 'Stop recording' : 'Start voice input'"
        @click="toggleListening"
      >
        <svg
          v-if="!isListening"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M12 15.5a3.5 3.5 0 0 0 3.5-3.5V6a3.5 3.5 0 1 0-7 0v6a3.5 3.5 0 0 0 3.5 3.5Z" />
          <path d="M5.5 11.5v.5a6.5 6.5 0 0 0 13 0v-.5M12 18.5V22M9 22h6" />
        </svg>
        <svg
          v-else
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
          class="stop-icon"
        >
          <rect x="7" y="7" width="10" height="10" rx="1.5" />
        </svg>
        <span class="microphone-button__pulse" />
      </button>
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
import { ref, nextTick, onBeforeUnmount, onMounted, watch } from 'vue';

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface Props {
  disabled?: boolean;
  recognitionLanguage?: string;
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  recognitionLanguage: 'en-US'
});

const emit = defineEmits<{
  send: [message: string];
}>();

const message = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isListening = ref(false);
const speechRecognitionSupported = ref(false);
let recognition: SpeechRecognitionLike | null = null;
let messageBeforeListening = '';
let finalTranscript = '';

const maxLines = 4;
const lineHeight = 24;

onMounted(() => {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
  speechRecognitionSupported.value = Boolean(Recognition);

  if (Recognition) {
    recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      isListening.value = true;
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) finalTranscript += result[0].transcript;
        else interimTranscript += result[0].transcript;
      }

      const separator = messageBeforeListening && (finalTranscript || interimTranscript) ? ' ' : '';
      message.value = `${messageBeforeListening}${separator}${finalTranscript}${interimTranscript}`;
      adjustHeight();
    };

    recognition.onerror = () => {
      isListening.value = false;
    };

    recognition.onend = () => {
      isListening.value = false;
      nextTick(() => textareaRef.value?.focus());
    };
  }

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
    } else if (isListening.value) {
      recognition?.stop();
    }
  }
);

watch(
  () => props.recognitionLanguage,
  (language) => {
    if (recognition) recognition.lang = language;
  },
  { immediate: true }
);

onBeforeUnmount(() => recognition?.abort());

const toggleListening = () => {
  if (!recognition || props.disabled) return;

  if (isListening.value) {
    recognition.stop();
    return;
  }

  messageBeforeListening = message.value.trimEnd();
  finalTranscript = '';
  recognition.lang = props.recognitionLanguage;

  try {
    recognition.start();
  } catch {}
};

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

  if (isListening.value) recognition?.stop();

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
  padding: 16px;
  background: #1a1a2e;
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

.input-wrapper--listening {
  border-color: #dc2626;
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.14);
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

.send-button,
.microphone-button {
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

.microphone-button {
  position: relative;
  overflow: visible;
  border: 1px solid #c7d2fe;
  border-radius: 50%;
  background: #eef2ff;
  color: #283593;
}

.microphone-button:hover:not(:disabled) {
  background: #dfe5ff;
}

.microphone-button--listening {
  border-color: #dc2626;
  border-radius: 8px;
  background: #dc2626;
  color: #ffffff;
  transform: scale(1.04);
}

.microphone-button--listening:hover:not(:disabled) {
  background: #b91c1c;
}

.microphone-button svg {
  width: 21px;
  height: 21px;
  display: block;
  pointer-events: none;
}

.microphone-button .stop-icon {
  width: 24px;
  height: 24px;
  stroke: none;
}

.microphone-button__pulse {
  display: none;
  position: absolute;
  inset: -4px;
  border: 2px solid #dc2626;
  border-radius: 11px;
}

.microphone-button--listening .microphone-button__pulse {
  display: block;
  animation: microphone-pulse 1.4s ease-out infinite;
}

.microphone-button:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

@keyframes microphone-pulse {
  from { opacity: 0.7; transform: scale(0.94); }
  to { opacity: 0; transform: scale(1.16); }
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
