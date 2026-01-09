<template>
  <div class="chat-history">
    <div class="messages-container" ref="messagesContainer">
      <slot></slot>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, onUpdated } from 'vue';

export default defineComponent({
  name: 'ChatHistory',
  setup() {
    const messagesContainer = ref<HTMLElement | null>(null);

    const scrollToBottom = () => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
      }
    };

    onMounted(() => {
      scrollToBottom();
    });

    onUpdated(() => {
      scrollToBottom();
    });

    return {
      messagesContainer
    };
  }
});
</script>

<style scoped>
.chat-history {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  pointer-events: none;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  padding-bottom: 120px; /* Space for the input - adjust if needed */
  display: flex;
  flex-direction: column;
  gap: 16px;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f3f4f6;
  pointer-events: auto;
}

/* Webkit browsers (Chrome, Safari, Edge) */
.messages-container::-webkit-scrollbar {
  width: 10px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f3f4f6;
  border-radius: 5px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 5px;
  border: 2px solid #f3f4f6;
  background-clip: padding-box;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
  border: 2px solid #f3f4f6;
  background-clip: padding-box;
}
</style>