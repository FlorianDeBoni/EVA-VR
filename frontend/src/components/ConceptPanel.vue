<script setup>
import { computed } from "vue";

const props = defineProps({ conversation: { type: Object, required: true } });

const concept = computed(() => props.conversation.concept);
// A new search replaces the references under the same URL: the revision refreshes the <img>.
const referenceUrl = (position) =>
  props.conversation.imageUrl({
    kind: "references",
    id: position,
    revision: concept.value.references_revision,
  });
const latestUrl = computed(() =>
  props.conversation.imageUrl({ kind: "images", id: concept.value.latest_version }),
);
</script>

<template>
  <aside class="concept">
    <h2>Concept design</h2>

    <p v-if="!concept?.reference_count && !concept?.latest_version" class="empty">
      Looking for reference images…
    </p>

    <div v-if="concept?.reference_count" class="references">
      <figure v-for="n in concept.reference_count" :key="n">
        <figcaption>Reference {{ n }}</figcaption>
        <img :src="referenceUrl(n)" :alt="`Reference ${n}`" />
      </figure>
    </div>

    <figure v-if="concept?.latest_version">
      <figcaption>
        Concept, version {{ concept.latest_version }}
        <span class="badge" :class="{ validated: concept.is_validated }">
          {{ concept.is_validated ? "validated" : "draft" }}
        </span>
      </figcaption>
      <img :src="latestUrl" :alt="`Concept version ${concept.latest_version}`" />
    </figure>
  </aside>
</template>
