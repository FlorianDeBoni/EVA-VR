<script setup>
import { computed, reactive, ref } from "vue";

import ChatPanel from "./components/ChatPanel.vue";
import ConceptPanel from "./components/ConceptPanel.vue";
import HealthButton from "./components/HealthButton.vue";
import DetailedPanel from "./components/DetailedPanel.vue";
import InformationPanel from "./components/InformationPanel.vue";
import SpatialPanel from "./components/SpatialPanel.vue";
import ValidateButton from "./components/ValidateButton.vue";
import VrButton from "./components/VrButton.vue";
import { Conversation, STEPS } from "./conversation.js";
import { api } from "./services.js";

// The conversation (session id, history, gathered information) lives here, in the browser.
const conversation = reactive(new Conversation(api));

// The side panel is a tab: closed by default, so the chat takes the whole width.
const panelOpen = ref(false);
const PANEL_LABELS = ["Information", "Concept", "Spatial design", "Details"];
const panelLabel = computed(() => PANEL_LABELS[(conversation.step ?? 1) - 1]);
</script>

<template>
  <div class="app">
    <header>
      <h1>EVA-VR</h1>
      <span v-if="conversation.step" class="step" title="Current step of the workshop">
        Step {{ conversation.step }}/{{ STEPS.length }} · {{ STEPS[conversation.step - 1] }}
      </span>
      <span class="session" title="Session id of this conversation">{{ conversation.sessionId }}</span>
      <ValidateButton :conversation="conversation" />
      <VrButton :conversation="conversation" />
      <HealthButton />
      <button type="button" @click="conversation.reset()">New conversation</button>
    </header>

    <main>
      <ChatPanel :conversation="conversation" />
      <template v-if="panelOpen">
        <ConceptPanel v-if="conversation.step === 2" :conversation="conversation" />
        <SpatialPanel v-else-if="conversation.step === 3" :conversation="conversation" />
        <DetailedPanel v-else-if="conversation.step === 4" :conversation="conversation" />
        <InformationPanel v-else :information="conversation.information" />
      </template>
      <button
        type="button"
        class="panel-tab"
        :class="{ open: panelOpen }"
        :aria-expanded="panelOpen"
        @click="panelOpen = !panelOpen"
      >
        {{ panelLabel }} {{ panelOpen ? "›" : "‹" }}
      </button>
    </main>
  </div>
</template>
