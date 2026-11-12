import assert from "node:assert/strict";
import { test } from "node:test";

import { Conversation, newImages, STEPS } from "../src/conversation.js";

const INFO = { user_type: "kids", is_validated: false };

function fakeApi(handler) {
  const calls = [];
  return {
    calls,
    async chat(sessionId, messages) {
      calls.push({ sessionId, messages });
      return handler(sessionId, messages);
    },
  };
}

const ids = () => {
  let n = 0;
  return () => `session-${++n}`;
};

test("a conversation starts with a new session id and an empty history", () => {
  const conversation = new Conversation(fakeApi(), ids());
  assert.equal(conversation.sessionId, "session-1");
  assert.deepEqual(conversation.messages, []);
  assert.equal(conversation.information, null);
});

test("each turn sends the whole history and keeps both messages", async () => {
  const api = fakeApi((sessionId) => ({ session_id: sessionId, reply: "ok", information: INFO }));
  const conversation = new Conversation(api, ids());

  assert.equal(await conversation.send("one"), "ok");
  await conversation.send("two");

  assert.deepEqual(api.calls[0].messages, [{ role: "user", content: "one" }]);
  assert.deepEqual(api.calls[1].messages, [
    { role: "user", content: "one" },
    { role: "assistant", content: "ok" },
    { role: "user", content: "two" },
  ]);
  assert.equal(api.calls[1].sessionId, "session-1");
  assert.equal(conversation.messages.length, 4);
  assert.deepEqual(conversation.information, INFO);
});

test("a failed turn leaves the history untouched so it can be retried", async () => {
  let fail = true;
  const api = fakeApi((sessionId) => {
    if (fail) throw new Error("boom");
    return { session_id: sessionId, reply: "ok", information: INFO };
  });
  const conversation = new Conversation(api, ids());

  await assert.rejects(conversation.send("hello"), /boom/);
  assert.deepEqual(conversation.messages, []);

  fail = false;
  await conversation.send("hello");
  assert.equal(conversation.messages.length, 2);
});

test("reset gives a new session id and clears everything", async () => {
  const api = fakeApi((sessionId) => ({ session_id: sessionId, reply: "ok", information: INFO }));
  const conversation = new Conversation(api, ids());
  await conversation.send("hello");

  conversation.reset();

  assert.equal(conversation.sessionId, "session-2");
  assert.deepEqual(conversation.messages, []);
  assert.equal(conversation.information, null);
});

test("a reply that arrives after a reset is ignored", async () => {
  let release;
  const api = fakeApi(
    (sessionId) =>
      new Promise((resolve) => {
        release = () => resolve({ session_id: sessionId, reply: "late", information: INFO });
      }),
  );
  const conversation = new Conversation(api, ids());

  const pending = conversation.send("hello");
  conversation.reset();
  release();

  assert.equal(await pending, null);
  assert.deepEqual(conversation.messages, []);
  assert.equal(conversation.information, null);
});

test("start sends an empty query and keeps the welcome message as the first one", async () => {
  const api = fakeApi((sessionId) => ({ session_id: sessionId, reply: "Welcome!", information: INFO }));
  const conversation = new Conversation(api, ids());

  assert.equal(await conversation.start(), "Welcome!");

  assert.deepEqual(api.calls[0], { sessionId: "session-1", messages: [] });
  assert.deepEqual(conversation.messages, [{ role: "assistant", content: "Welcome!" }]);
  assert.deepEqual(conversation.information, INFO);

  await conversation.send("hello");
  assert.deepEqual(api.calls[1].messages, [
    { role: "assistant", content: "Welcome!" },
    { role: "user", content: "hello" },
  ]);
});

test("a failed start leaves the conversation empty and usable", async () => {
  let fail = true;
  const api = fakeApi((sessionId) => {
    if (fail) throw new Error("boom");
    return { session_id: sessionId, reply: "ok", information: INFO };
  });
  const conversation = new Conversation(api, ids());

  await assert.rejects(conversation.start(), /boom/);
  assert.deepEqual(conversation.messages, []);

  fail = false;
  await conversation.send("hello");
  assert.equal(conversation.messages.length, 2);
});

test("a welcome that arrives after a reset is ignored", async () => {
  let release;
  const api = fakeApi(
    (sessionId) =>
      new Promise((resolve) => {
        release = () => resolve({ session_id: sessionId, reply: "late", information: INFO });
      }),
  );
  const conversation = new Conversation(api, ids());

  const pending = conversation.start();
  conversation.reset();
  release();

  assert.equal(await pending, null);
  assert.deepEqual(conversation.messages, []);
});

test("the concept progress of the last reply is kept and reset with the conversation", async () => {
  const concept = { reference_count: 3, latest_version: 1, is_validated: false };
  const api = fakeApi((sessionId) => ({ session_id: sessionId, reply: "ok", information: INFO, concept }));
  const conversation = new Conversation(api, ids());

  await conversation.send("hello");
  assert.deepEqual(conversation.concept, concept);

  conversation.reset();
  assert.equal(conversation.concept, null);
});

const progress = (extra) => ({
  reference_count: 0,
  latest_version: null,
  is_validated: false,
  references_revision: null,
  ...extra,
});

test("newImages brings the references once per search and each new concept version", () => {
  const refs = progress({ reference_count: 2, references_revision: 10 });
  const generated = { ...refs, latest_version: 1 };

  assert.deepEqual(newImages(null, progress()), []);
  assert.deepEqual(newImages(null, refs), [
    { kind: "references", id: 1, revision: 10 },
    { kind: "references", id: 2, revision: 10 },
  ]);
  assert.deepEqual(newImages(refs, generated), [{ kind: "images", id: 1 }]);
  assert.deepEqual(newImages(generated, generated), []);
  // A new search under the same count is a new set of references.
  assert.equal(newImages(generated, { ...generated, references_revision: 11 }).length, 2);
});

test("a reply carries the step and the images it produced, and they stay in the browser", async () => {
  const replies = [
    { step: 1, concept: progress() },
    { step: 2, concept: progress({ reference_count: 1, references_revision: 5 }) },
    { step: 2, concept: progress({ reference_count: 1, references_revision: 5, latest_version: 1 }) },
  ];
  const api = fakeApi(() => ({ reply: "ok", information: INFO, ...replies.shift() }));
  api.conceptImageUrl = (sessionId, kind, id) => `http://api/${sessionId}/${kind}/${id}`;
  const conversation = new Conversation(api, ids());

  await conversation.send("one");
  assert.equal(conversation.step, 1);
  assert.equal(conversation.messages[1].images, undefined);

  await conversation.send("two");
  await conversation.send("three");

  assert.equal(conversation.step, 2);
  const [, , , second, , third] = conversation.messages;
  assert.deepEqual(second.images, [{ kind: "references", id: 1, revision: 5 }]);
  assert.deepEqual(third.images, [{ kind: "images", id: 1 }]);
  // The API only gets roles and texts.
  assert.deepEqual(Object.keys(api.calls[2].messages[3]), ["role", "content"]);
  assert.equal(conversation.imageUrl(second.images[0]), "http://api/session-1/references/1?r=5");
  assert.equal(conversation.imageUrl(third.images[0]), "http://api/session-1/images/1");
});

test("references replaced by a newer search are no longer current", async () => {
  const api = fakeApi(() => ({
    reply: "ok",
    information: INFO,
    step: 2,
    concept: progress({ reference_count: 1, references_revision: 7 }),
  }));
  const conversation = new Conversation(api, ids());
  await conversation.send("hello");

  assert.equal(conversation.isCurrent({ kind: "references", id: 1, revision: 7 }), true);
  assert.equal(conversation.isCurrent({ kind: "references", id: 1, revision: 6 }), false);
  assert.equal(conversation.isCurrent({ kind: "images", id: 1 }), true);
});

test("reset forgets the step", async () => {
  const api = fakeApi(() => ({ reply: "ok", information: INFO, step: 2, concept: progress() }));
  const conversation = new Conversation(api, ids());
  await conversation.send("hello");

  conversation.reset();

  assert.equal(conversation.step, null);
});

test("the spatial design of the last reply is kept and reset with the conversation", async () => {
  const design = { spaces: [{ name: "Lab" }], relationships: [], is_validated: false };
  const api = fakeApi(() => ({
    reply: "ok",
    information: INFO,
    step: 3,
    concept: progress(),
    spatial_design: design,
  }));
  const conversation = new Conversation(api, ids());

  await conversation.send("hello");
  assert.equal(conversation.step, 3);
  assert.deepEqual(conversation.spatialDesign, design);

  conversation.reset();
  assert.equal(conversation.spatialDesign, null);
});

test("step 3 is named", () => {
  assert.equal(STEPS[2], "Spatial design");
});

test("a picture generated in step 3 is shown in the chat like any new image", async () => {
  const replies = [
    { step: 3, concept: progress({ reference_count: 3, latest_version: 2, is_validated: true, references_revision: 5 }) },
    { step: 3, concept: progress({ reference_count: 3, latest_version: 3, is_validated: true, references_revision: 5 }) },
  ];
  const api = fakeApi(() => ({ reply: "ok", information: INFO, spatial_design: { spaces: [] }, ...replies.shift() }));
  const conversation = new Conversation(api, ids());

  await conversation.send("one");
  await conversation.send("draw it");

  // The first reply of the session brings the references; the second only the new picture.
  assert.deepEqual(conversation.messages[3].images, [{ kind: "images", id: 3 }]);
});

test("the detailed design of the last reply is kept and reset with the conversation", async () => {
  const design = { details: [{ name: "Table" }], latest_image_version: 4, is_validated: true };
  const api = fakeApi(() => ({
    reply: "ok",
    information: INFO,
    step: 4,
    concept: progress(),
    detailed_design: design,
  }));
  const conversation = new Conversation(api, ids());

  await conversation.send("hello");
  assert.equal(conversation.step, 4);
  assert.deepEqual(conversation.detailedDesign, design);

  conversation.reset();
  assert.equal(conversation.detailedDesign, null);
});

test("step 4 is named, and a final picture is shown in the chat like any new image", async () => {
  assert.equal(STEPS[3], "Detailed design");
  const replies = [
    { step: 4, concept: progress({ latest_version: 5, is_validated: true }) },
    { step: 4, concept: progress({ latest_version: 6, is_validated: true }) },
  ];
  const api = fakeApi(() => ({ reply: "ok", information: INFO, detailed_design: { details: [] }, ...replies.shift() }));
  const conversation = new Conversation(api, ids());

  await conversation.send("one");
  await conversation.send("draw it");

  assert.deepEqual(conversation.messages[3].images, [{ kind: "images", id: 6 }]);
});

test("the spatial picture and the final picture have their own urls", () => {
  const conversation = new Conversation(
    { conceptImageUrl: (s, kind, id) => `http://api/${s}/${kind}${id === undefined ? "" : `/${id}`}` },
    () => "s1",
  );

  assert.equal(conversation.imageUrl({ kind: "spatial" }), "http://api/s1/spatial");
  assert.equal(conversation.imageUrl({ kind: "final" }), "http://api/s1/final");
});

const withFinalPicture = (extra = {}) => ({
  step: 4,
  detailedDesign: { details: [], latest_image_version: 6, is_validated: false },
  ...extra,
});

test("the final version can be validated while a picture of step 4 is waiting for it", () => {
  const conversation = new Conversation(fakeApi(), ids());
  assert.equal(conversation.canValidateFinal, false); // nothing yet

  Object.assign(conversation, withFinalPicture());
  assert.equal(conversation.canValidateFinal, true);

  Object.assign(conversation, withFinalPicture({ step: 3 }));
  assert.equal(conversation.canValidateFinal, false); // another step

  Object.assign(conversation, withFinalPicture({ detailedDesign: { details: [], latest_image_version: null, is_validated: false } }));
  assert.equal(conversation.canValidateFinal, false); // no picture yet

  Object.assign(conversation, withFinalPicture({ detailedDesign: { details: [], latest_image_version: 6, is_validated: true } }));
  assert.equal(conversation.canValidateFinal, false); // already accepted
});

test("validateFinal sends the latest picture and keeps the validated design", async () => {
  const validated = { details: [], latest_image_version: 6, is_validated: true };
  const api = { ...fakeApi(), calls: [], async validateDetailedDesign(sessionId, version) {
    this.calls.push({ sessionId, version });
    return validated;
  } };
  const conversation = new Conversation(api, ids());
  Object.assign(conversation, withFinalPicture());

  assert.deepEqual(await conversation.validateFinal(), validated);

  assert.deepEqual(api.calls, [{ sessionId: "session-1", version: 6 }]);
  assert.deepEqual(conversation.detailedDesign, validated);
  assert.equal(conversation.canValidateFinal, false);
});

test("a refused validation changes nothing so the button can be pressed again", async () => {
  const api = { ...fakeApi(), async validateDetailedDesign() { throw new Error("no furniture"); } };
  const conversation = new Conversation(api, ids());
  Object.assign(conversation, withFinalPicture());

  await assert.rejects(conversation.validateFinal(), /no furniture/);

  assert.equal(conversation.detailedDesign.is_validated, false);
  assert.equal(conversation.canValidateFinal, true);
});

test("a validation that comes back after a reset is dropped", async () => {
  let answer;
  const api = { ...fakeApi(), validateDetailedDesign: () => new Promise((resolve) => (answer = resolve)) };
  const conversation = new Conversation(api, ids());
  Object.assign(conversation, withFinalPicture());

  const pending = conversation.validateFinal();
  conversation.reset();
  answer({ details: [], latest_image_version: 6, is_validated: true });

  assert.equal(await pending, null);
  assert.equal(conversation.detailedDesign, null);
});
