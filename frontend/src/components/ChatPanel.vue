<script setup>
import { nextTick, onMounted, ref, watch } from "vue";

import { api } from "../services.js";
import { hasSpeech, Recorder } from "../speech.js";

const props = defineProps({ conversation: { type: Object, required: true } });

const input = ref("");
const pendingText = ref(null); // the message being sent, shown before the reply arrives
const starting = ref(false); // waiting for the welcome message
const errors = ref([]); // shown in the chat, never part of the history
const recording = ref(false);
const transcribing = ref(false);
const messagesEl = ref(null);
const recorder = new Recorder();
const speechLimits = {
  minMs: Number(import.meta.env.VITE_STT_MIN_MS),
  minLevel: Number(import.meta.env.VITE_STT_MIN_LEVEL),
};

const busy = () => pendingText.value !== null || starting.value;

// An empty query makes the assistant open the conversation with a welcome message.
async function welcome() {
  const sessionId = props.conversation.sessionId;
  starting.value = true;
  try {
    await props.conversation.start();
  } catch (error) {
    if (props.conversation.sessionId === sessionId) errors.value = [error.message];
  } finally {
    if (props.conversation.sessionId === sessionId) starting.value = false;
  }
}

// A new conversation starts from a clean panel, with a new welcome message.
watch(
  () => props.conversation.sessionId,
  () => {
    input.value = "";
    pendingText.value = null;
    errors.value = [];
    welcome();
  },
);

onMounted(welcome);

// Keep the latest message in view (again when its images finish loading and make it taller).
async function scrollDown() {
  await nextTick();
  messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
}

watch(() => [props.conversation.messages.length, pendingText.value, errors.value.length], scrollDown);

async function send() {
  const text = input.value.trim();
  if (!text || busy()) return;

  const sessionId = props.conversation.sessionId;
  input.value = "";
  errors.value = [];
  pendingText.value = text;
  try {
    await props.conversation.send(text);
  } catch (error) {
    // Nothing was added to the history: the text goes back in the box to be sent again.
    if (props.conversation.sessionId === sessionId) {
      input.value = text;
      errors.value = [error.message];
    }
  } finally {
    if (props.conversation.sessionId === sessionId) pendingText.value = null;
  }
}

// Speech to text: the transcript goes in the box, it is not sent.
async function toggleRecording() {
  if (!recording.value) {
    try {
      await recorder.start();
      recording.value = true;
    } catch (error) {
      errors.value = [`Microphone unavailable: ${error.message}`];
    }
    return;
  }

  recording.value = false;
  transcribing.value = true;
  try {
    const { blob, filename, durationMs, peak } = await recorder.stop();
    if (!hasSpeech({ peak, durationMs }, speechLimits)) {
      // Silence makes the speech model invent text: do not send it.
      errors.value = ["No speech detected, nothing was sent. Check your microphone and speak a bit longer."];
      return;
    }
    const text = (await api.transcribe(blob, filename)).trim();
    if (!text) {
      errors.value = ["No words were recognized. Try again."];
      return;
    }
    input.value = [input.value.trim(), text].filter(Boolean).join(" ");
  } catch (error) {
    errors.value = [`Speech to text failed: ${error.message}`];
  } finally {
    transcribing.value = false;
  }
}
</script>

<template>
  <section class="chat">
    <div ref="messagesEl" class="messages" aria-live="polite">
      <p v-if="!conversation.messages.length && pendingText === null && !starting" class="empty">
        The assistant could not open the conversation. Say hello to start.
      </p>
      <div v-for="(message, i) in conversation.messages" :key="i" class="message" :class="message.role">
        {{ message.content }}
        <div v-if="message.images?.some((image) => conversation.isCurrent(image))" class="images">
          <template v-for="image in message.images" :key="`${image.kind}${image.id}`">
            <img
              v-if="conversation.isCurrent(image)"
              :class="`image-${image.kind}`"
              :src="conversation.imageUrl(image)"
              :alt="image.kind === 'references' ? `Reference ${image.id}` : `Concept version ${image.id}`"
              @load="scrollDown"
            />
          </template>
        </div>
      </div>
      <div v-if="starting" class="message assistant pending">…</div>
      <template v-if="pendingText !== null">
        <div class="message user">{{ pendingText }}</div>
        <div class="message assistant pending">…</div>
      </template>
      <div v-for="(error, i) in errors" :key="`e${i}`" class="message error">{{ error }}</div>
    </div>

    <form class="composer" @submit.prevent="send">
      <textarea
        v-model="input"
        rows="2"
        placeholder="Type your answer… (Enter to send)"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button
        type="button"
        class="mic"
        :class="{ recording }"
        :disabled="transcribing"
        title="Dictate (the text is not sent)"
        @click="toggleRecording"
      >
        {{ transcribing ? "…" : recording ? "⏹" : "🎤" }}
      </button>
      <button type="submit" :disabled="pendingText !== null || starting">Send</button>
    </form>
  </section>
</template>
