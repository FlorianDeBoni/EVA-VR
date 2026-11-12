import assert from "node:assert/strict";
import { test } from "node:test";

import { Conversation, newImages } from "../src/conversation.js";

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
