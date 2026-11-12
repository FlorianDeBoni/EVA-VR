<script setup>
defineProps({ information: { type: Object, default: null } });

const FIELDS = [
  ["user_type", "Who uses the room"],
  ["number_of_users", "How many at once"],
  ["task_description", "Creative task"],
  ["goal", "Goal"],
  ["must_have_features", "Must-have features"],
];

function display(value) {
  const text = Array.isArray(value) ? value.join(", ") : value;
  return text === undefined || text === null || text === "" ? "—" : text;
}
</script>

<template>
  <aside class="information">
    <h2>Gathered so far</h2>
    <dl>
      <template v-for="[key, label] in FIELDS" :key="key">
        <dt>{{ label }}</dt>
        <dd>{{ display(information?.[key]) }}</dd>
      </template>
      <dt>Validated</dt>
      <dd>
        <span class="badge" :class="{ validated: information?.is_validated }">
          {{ information?.is_validated ? "yes" : "no" }}
        </span>
      </dd>
    </dl>
  </aside>
</template>
