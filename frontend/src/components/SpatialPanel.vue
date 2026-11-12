<script setup>
import { computed } from "vue";

const props = defineProps({ conversation: { type: Object, required: true } });

const design = computed(() => props.conversation.spatialDesign);
// The concept the spatial design starts from: it was validated to get to this step.
const conceptUrl = computed(() => props.conversation.imageUrl({ kind: "validated" }));
// The step ends with a picture of the organization: a refined version of that concept.
const pictureUrl = computed(() =>
  design.value?.latest_image_version
    ? props.conversation.imageUrl({ kind: "images", id: design.value.latest_image_version })
    : null,
);

const RELATIONS = {
  adjacent: "next to",
  open_connection: "open to",
  visual_link: "visible from",
  separated: "separated from",
  circulation: "path to",
};

function details(space) {
  return [
    space.capacity ? `${space.capacity} people` : null,
    space.size,
    space.activities.length ? space.activities.join(", ") : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
</script>

<template>
  <aside class="spatial">
    <h2>
      Spatial design
      <span class="badge" :class="{ validated: design?.is_validated }">
        {{ design?.is_validated ? "validated" : "draft" }}
      </span>
    </h2>

    <figure v-if="pictureUrl">
      <figcaption>Refined concept, version {{ design.latest_image_version }}</figcaption>
      <img :src="pictureUrl" :alt="`Refined concept version ${design.latest_image_version}`" />
    </figure>

    <figure>
      <figcaption>Concept it starts from</figcaption>
      <img :src="conceptUrl" alt="Validated concept" />
    </figure>

    <p v-if="!design?.spaces.length" class="empty">The assistant is drafting the spaces…</p>

    <template v-else>
      <h3>Spaces</h3>
      <ul>
        <li v-for="space in design.spaces" :key="space.name">
          <strong>{{ space.name }}</strong> — {{ space.purpose }}
          <small v-if="details(space)">{{ details(space) }}</small>
        </li>
      </ul>

      <h3 v-if="design.relationships.length">Relationships</h3>
      <ul>
        <li v-for="(link, i) in design.relationships" :key="i">
          <strong>{{ link.from_space }}</strong>
          <span class="relation"> {{ RELATIONS[link.type] ?? link.type }} </span>
          <strong>{{ link.to_space }}</strong>
          <small v-if="link.description">{{ link.description }}</small>
        </li>
      </ul>
    </template>
  </aside>
</template>
