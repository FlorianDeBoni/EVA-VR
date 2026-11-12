<script setup>
import { ref } from "vue";

const props = defineProps({ conversation: { type: Object, required: true } });

const busy = ref(false);
const error = ref(null);

// One click accepts the latest picture as the final design. The chat is not needed, and the
// server applies the same rules as the assistant: the reason is shown when it refuses.
async function validate() {
  const sessionId = props.conversation.sessionId;
  busy.value = true;
  error.value = null;
  try {
    await props.conversation.validateFinal();
  } catch (failure) {
    if (props.conversation.sessionId === sessionId) error.value = failure.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <!-- Only while there is a picture of the last step that was not accepted yet. -->
  <template v-if="conversation.canValidateFinal">
    <span v-if="error" class="validate-error" role="alert">{{ error }}</span>
    <button
      type="button"
      class="validate-button"
      title="Keep the latest picture as the final version of the room"
      :disabled="busy"
      @click="validate"
    >
      {{ busy ? "Validating…" : "Validate final version" }}
    </button>
  </template>
</template>
