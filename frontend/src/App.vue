<script setup>
import { reactive } from "vue";

import ChatPanel from "./components/ChatPanel.vue";
import HealthButton from "./components/HealthButton.vue";
import InformationPanel from "./components/InformationPanel.vue";
import { Conversation } from "./conversation.js";
import { api } from "./services.js";

// The conversation (session id, history, gathered information) lives here, in the browser.
const conversation = reactive(new Conversation(api));
</script>

<template>
  <div class="app">
    <header>
      <h1>EVA-VR</h1>
      <span class="session" title="Session id of this conversation">{{ conversation.sessionId }}</span>
      <HealthButton />
      <button type="button" @click="conversation.reset()">New conversation</button>
    </header>

    <main>
      <ChatPanel :conversation="conversation" />
      <InformationPanel :information="conversation.information" />
    </main>
  </div>
</template>
