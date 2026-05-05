<template>
  <div class="edit-save-container">
    <div class="edit-save-wrapper">
      <h1 class="edit-save-title">Editing System Prompt</h1>

      <EditField ref="editField" />
      <SaveButton @save="save" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

import EditField from './EditField.vue';
import SaveButton from './SaveButton.vue';

const editField = ref<InstanceType<typeof EditField> | null>(null);
const csrf_token = ref('');

onMounted(async () => {
  const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/csrf`, {
                        method: "GET",
                        credentials: "include",
                    });
  const res_json = await res.json();
  csrf_token.value = res_json.csrfToken;
})

const save = async () => {
    const updated_content = editField.value?.content;
    const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/updatePrompt`, {
        method: "POST",
        credentials: "include",
        headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token.value,
        },
        body: JSON.stringify({ prompt: updated_content }),
    });
    if (res.status === 200) {
        alert("Prompt updated successfully!");
    } else {
        alert("Failed to update prompt.");
    }
};
</script>

<style scoped>
.edit-save-container {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 16px;
}

.edit-save-wrapper {
  width: 75vw;
  max-width: 800px;

  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.edit-save-title {
  margin: 0;
  color: #000000;
  font-size: 28px;
  font-weight: 700;
  text-align: center;
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
}
</style>