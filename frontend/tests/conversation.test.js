import assert from "node:assert/strict";
import { test } from "node:test";

import { Conversation } from "../src/conversation.js";

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
