<script setup>
import { vrPageUrl } from "../links.js";

defineProps({ conversation: { type: Object, required: true } });
</script>

<template>
  <!-- Only once the user validated the final picture, through the assistant. -->
  <a
    v-if="conversation.detailedDesign?.is_validated"
    class="vr-button"
    :href="vrPageUrl(conversation.sessionId)"
    target="_blank"
    rel="noopener"
  >
    Go to VR
  </a>
</template>
