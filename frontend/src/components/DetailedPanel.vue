<script setup>
import { computed } from "vue";

const props = defineProps({ conversation: { type: Object, required: true } });

const design = computed(() => props.conversation.detailedDesign);
// The step ends with a picture: the final version of the spatial picture, with the details.
const pictureUrl = computed(() =>
  design.value?.latest_image_version
    ? props.conversation.imageUrl({ kind: "images", id: design.value.latest_image_version })
    : null,
);
// The picture validated in the previous step, whose layout this step keeps.
const spatialUrl = computed(() => props.conversation.imageUrl({ kind: "spatial" }));

const CATEGORIES = [
  ["furniture", "Furniture"],
  ["shape", "Shapes"],
  ["material", "Materials"],
  ["color", "Colors"],
  ["lighting", "Lighting"],
  ["accessory", "Accessories"],
];

// The details in a fixed order of categories, only the categories that have some.
const groups = computed(() =>
  CATEGORIES.map(([key, label]) => ({
    key,
    label,
    details: (design.value?.details ?? []).filter((detail) => detail.category === key),
  })).filter((group) => group.details.length),
);

function where(detail) {
  return [detail.space ?? "whole room", detail.quantity ? `× ${detail.quantity}` : null]
    .filter(Boolean)
    .join(" · ");
}
</script>

<template>
  <aside class="detailed">
    <h2>
      Detailed design
      <span class="badge" :class="{ validated: design?.is_validated }">
        {{ design?.is_validated ? "final" : "draft" }}
      </span>
    </h2>

    <p v-if="design?.is_validated" class="final">Final design saved. Use “Go to VR” to see it.</p>

    <figure v-if="pictureUrl">
      <figcaption>{{ design.is_validated ? "Final picture" : "Picture" }}, version {{ design.latest_image_version }}</figcaption>
      <img :src="pictureUrl" :alt="`Picture with the details, version ${design.latest_image_version}`" />
    </figure>

    <figure>
      <figcaption>Spatial picture it starts from</figcaption>
      <img :src="spatialUrl" alt="Validated spatial picture" />
    </figure>

    <p v-if="!groups.length" class="empty">The assistant is drafting the details…</p>

    <template v-for="group in groups" :key="group.key">
      <h3>{{ group.label }}</h3>
      <ul>
        <li v-for="detail in group.details" :key="`${detail.name}-${detail.space}`">
          <strong>{{ detail.name }}</strong> — {{ detail.description }}
          <small>{{ where(detail) }}</small>
        </li>
      </ul>
    </template>
  </aside>
</template>
