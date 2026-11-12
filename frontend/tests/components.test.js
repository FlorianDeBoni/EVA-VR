import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import vue from "@vitejs/plugin-vue";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";

import { Conversation } from "../src/conversation.js";

// Components are compiled by Vite and rendered to HTML on the server: no browser, no new
// dependency. This checks what each one shows for a given state (not mounted hooks or clicks).
let server;

before(async () => {
  server = await createServer({
    root: process.cwd(),
    configFile: false,
    plugins: [vue()],
    // Own cache, and no dependency optimizer: the default cache (node_modules/.vite) belongs to
    // the dev server, and two servers rebuilding it at once break it ("504 Outdated Optimize Dep").
    cacheDir: "node_modules/.vite-test",
    optimizeDeps: { noDiscovery: true, include: [] },
    logLevel: "silent",
    server: { middlewareMode: true },
    appType: "custom",
  });
});

after(() => server.close());

async function render(name, props) {
  const { default: component } = await server.ssrLoadModule(`/src/components/${name}.vue`);
  return renderToString(createSSRApp(component, props));
}

const api = {
  conceptImageUrl: (sessionId, kind, id) =>
    `http://api/${sessionId}/${kind}${id === undefined ? "" : `/${id}`}`,
};

/** A real conversation (so imageUrl / isCurrent behave for real) in a given state. */
function conversationWith(state) {
  const conversation = new Conversation(api, () => "s1");
  Object.assign(conversation, state);
  return conversation;
}

const count = (html, pattern) => (html.match(pattern) ?? []).length;

// ---- SpatialPanel

const LAB = { name: "Lab", purpose: "build prototypes", activities: ["sketching", "testing"], capacity: 4, size: "large" };
const LOUNGE = { name: "Lounge", purpose: "rest", activities: [], capacity: null, size: null };

test("the spatial panel shows the spaces and how they relate, as a draft", async () => {
  const conversation = conversationWith({
    step: 3,
    spatialDesign: {
      spaces: [LAB, LOUNGE],
      relationships: [{ from_space: "Lab", to_space: "Lounge", type: "visual_link", description: "see each other" }],
      is_validated: false,
    },
  });

  const html = await render("SpatialPanel", { conversation });

  assert.match(html, /<strong>Lab<\/strong> — build prototypes/);
  assert.match(html, /4 people · large · sketching, testing/);
  assert.match(html, /<strong>Lounge<\/strong> — rest/);
  assert.match(html, /<strong>Lab<\/strong><span class="relation">\s*visible from\s*<\/span><strong>Lounge<\/strong>/);
  assert.match(html, /see each other/);
  assert.match(html, /<span class="badge">draft<\/span>/);
});

test("the spatial panel shows the refined picture above the concept it starts from", async () => {
  const conversation = conversationWith({
    step: 3,
    spatialDesign: { spaces: [LAB], relationships: [], latest_image_version: 5, is_validated: false },
  });

  const html = await render("SpatialPanel", { conversation });

  assert.match(html, /Refined concept, version 5/);
  assert.ok(html.includes("http://api/s1/images/5"));
  // The picture comes first, the validated concept it refines after it.
  assert.ok(html.indexOf("images/5") < html.indexOf("s1/validated"));
  assert.equal(count(html, /<img/g), 2);
});

test("the spatial panel shows no picture until one was generated", async () => {
  const conversation = conversationWith({
    step: 3,
    spatialDesign: { spaces: [LAB], relationships: [], latest_image_version: null, is_validated: false },
  });

  const html = await render("SpatialPanel", { conversation });

  assert.equal(count(html, /Refined concept/g), 0);
  assert.equal(count(html, /<img/g), 1);
});

test("the spatial panel starts from the validated concept image", async () => {
  const html = await render("SpatialPanel", { conversation: conversationWith({ step: 3 }) });

  assert.match(html, /<img src="http:\/\/api\/s1\/validated"/);
});

test("the spatial panel says the assistant is drafting while there is no space", async () => {
  const html = await render("SpatialPanel", {
    conversation: conversationWith({ spatialDesign: { spaces: [], relationships: [], is_validated: false } }),
  });

  assert.match(html, /drafting the spaces/);
  assert.equal(count(html, /<li>/g), 0);
});

test("the spatial panel flags a validated design", async () => {
  const html = await render("SpatialPanel", {
    conversation: conversationWith({ spatialDesign: { spaces: [LAB], relationships: [], is_validated: true } }),
  });

  assert.match(html, /<span class="validated badge">validated<\/span>/);
  assert.equal(count(html, /<h3>Relationships<\/h3>/g), 0);
});

test("the spatial panel names every kind of relationship in plain words", async () => {
  const types = ["adjacent", "open_connection", "visual_link", "separated", "circulation"];
  const html = await render("SpatialPanel", {
    conversation: conversationWith({
      spatialDesign: {
        spaces: [LAB, LOUNGE],
        relationships: types.map((type) => ({ from_space: "Lab", to_space: "Lounge", type, description: "" })),
        is_validated: false,
      },
    }),
  });

  for (const words of ["next to", "open to", "visible from", "separated from", "path to"]) {
    assert.ok(html.includes(words), words);
  }
});

// ---- ConceptPanel

test("the concept panel waits for the references", async () => {
  const concept = { reference_count: 0, latest_version: null, is_validated: false, references_revision: null };

  const html = await render("ConceptPanel", { conversation: conversationWith({ step: 2, concept }) });

  assert.match(html, /Looking for reference images/);
  assert.equal(count(html, /<img/g), 0);
});

test("the concept panel shows the references one under the other, then the latest concept", async () => {
  const concept = { reference_count: 3, latest_version: 2, is_validated: false, references_revision: 77 };

  const html = await render("ConceptPanel", { conversation: conversationWith({ step: 2, concept }) });

  assert.equal(count(html, /<img/g), 4);
  assert.ok(html.includes("http://api/s1/references/1?r=77"));
  assert.ok(html.includes("http://api/s1/references/3?r=77"));
  assert.ok(html.includes("http://api/s1/images/2"));
  assert.match(html, /Concept, version 2/);
  assert.match(html, /<span class="badge">draft<\/span>/);
});

test("the concept panel flags a validated concept", async () => {
  const concept = { reference_count: 1, latest_version: 1, is_validated: true, references_revision: 1 };

  const html = await render("ConceptPanel", { conversation: conversationWith({ concept }) });

  assert.match(html, /<span class="validated badge">validated<\/span>/);
});

// ---- InformationPanel

test("the information panel lists what was gathered and whether it is validated", async () => {
  const information = {
    user_type: "architects",
    number_of_users: 5,
    task_description: null,
    goal: "find ideas",
    must_have_features: ["whiteboard", "daylight"],
    is_validated: false,
  };

  const html = await render("InformationPanel", { information });

  assert.match(html, /architects/);
  assert.match(html, /whiteboard, daylight/);
  assert.match(html, /<dd>—<\/dd>/); // the task is not known yet
  assert.match(html, /<span class="badge">no<\/span>/);
});

// ---- ChatPanel

test("the chat shows the images of a reply, in a column, and hides replaced references", async () => {
  const conversation = conversationWith({
    concept: { reference_count: 2, latest_version: 1, is_validated: false, references_revision: 9 },
    messages: [
      { role: "user", content: "hello" },
      {
        role: "assistant",
        content: "old references",
        images: [{ kind: "references", id: 1, revision: 8 }],
      },
      {
        role: "assistant",
        content: "new references and a concept",
        images: [
          { kind: "references", id: 1, revision: 9 },
          { kind: "references", id: 2, revision: 9 },
          { kind: "images", id: 1 },
        ],
      },
    ],
  });

  const html = await render("ChatPanel", { conversation });

  assert.match(html, /class="user message">\s*hello/);
  // The references of revision 8 were replaced by a new search: only revision 9 is shown.
  assert.equal(count(html, /references\/\d\?r=8/g), 0);
  assert.equal(count(html, /<img/g), 3);
  assert.ok(html.includes("http://api/s1/references/2?r=9"));
  assert.ok(html.includes("http://api/s1/images/1"));
  // The message whose references were all replaced has no empty image block left.
  assert.equal(count(html, /<div class="images">/g), 1);
  // The image kind must not reuse the container's class: its CSS would apply to the image.
  assert.equal(count(html, /<img class="images"/g), 0);
  assert.equal(count(html, /<img class="image-references"/g), 2);
  assert.equal(count(html, /<img class="image-images"/g), 1);
});

test("the chat shows plain replies without any image block", async () => {
  const conversation = conversationWith({
    messages: [{ role: "assistant", content: "Who will use the room?" }],
  });

  const html = await render("ChatPanel", { conversation });

  assert.match(html, /Who will use the room\?/);
  assert.equal(count(html, /<img/g), 0);
  assert.equal(count(html, /<div class="images">/g), 0);
});
