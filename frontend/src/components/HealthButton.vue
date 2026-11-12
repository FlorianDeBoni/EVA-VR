<script setup>
import { onMounted, onUnmounted, ref } from "vue";

import { api } from "../services.js";

// null = not checked yet, true = green, false = red
const up = ref(null);
let timer;

async function check() {
  up.value = await api.health();
}

onMounted(() => {
  check();
  timer = setInterval(check, Number(import.meta.env.VITE_HEALTH_POLL_MS));
});
onUnmounted(() => clearInterval(timer));
</script>

<template>
  <button
    type="button"
    class="health"
    :class="{ up: up === true, down: up === false }"
    title="Check the API now"
    @click="check"
  >
    <span class="dot"></span>
    {{ up === null ? "API…" : up ? "API online" : "API offline" }}
  </button>
</template>
