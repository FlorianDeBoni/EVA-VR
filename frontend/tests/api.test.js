import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError, createApi } from "../src/api.js";

const json = (status, body) => ({ ok: status < 400, status, json: async () => body });

test("health is true when the API answers ok, false otherwise, and never throws", async () => {
  const urls = [];
  const ok = createApi("http://api/", async (url) => (urls.push(url), json(200, {})));
  assert.equal(await ok.health(), true);
  assert.deepEqual(urls, ["http://api/health/ready"]);

  assert.equal(await createApi("http://api", async () => json(503, {})).health(), false);
  const down = createApi("http://api", async () => {
    throw new TypeError("fetch failed");
  });
  assert.equal(await down.health(), false);
});

test("chat posts the session id and the whole history as json", async () => {
  let call;
  const api = createApi("http://api", async (url, init) => {
    call = { url, init };
    return json(200, { session_id: "s", reply: "hi", information: {} });
  });
  const messages = [{ role: "user", content: "hello" }];

  const body = await api.chat("s", messages);

  assert.equal(call.url, "http://api/chat");
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(call.init.body), { session_id: "s", messages });
  assert.equal(body.reply, "hi");
});

test("chat surfaces the API error detail", async () => {
  const api = createApi("http://api", async () => json(503, { detail: "run `task seed:prompts`" }));

  await assert.rejects(api.chat("s", []), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 503);
    assert.match(error.message, /seed:prompts/);
    return true;
  });
});

test("validation errors (detail as a list) are readable", async () => {
  const api = createApi("http://api", async () => json(422, { detail: [{ msg: "bad" }] }));
  await assert.rejects(api.chat("s", []), /bad/);
});

test("an unreachable API gives a clear error with status 0", async () => {
  const api = createApi("http://api", async () => {
    throw new TypeError("fetch failed");
  });
  await assert.rejects(api.chat("s", []), (error) => error.status === 0 && /Cannot reach/.test(error.message));
});

test("transcribe uploads the audio as multipart and returns the text", async () => {
  let init;
  const api = createApi("http://api", async (url, options) => {
    init = options;
    assert.equal(url, "http://api/speech/transcribe");
    return json(200, { text: "hello world" });
  });

  const text = await api.transcribe(new Blob(["x"], { type: "audio/webm" }), "recording.webm");

  assert.equal(text, "hello world");
  assert.ok(init.body instanceof FormData);
  assert.equal(init.body.get("file").name, "recording.webm");
});

test("conceptImageUrl builds the URL of each kind of concept image", () => {
  const api = createApi("http://api.test/");

  assert.equal(api.conceptImageUrl("s1", "references", 2), "http://api.test/concept/s1/references/2");
  assert.equal(api.conceptImageUrl("s1", "images", 3), "http://api.test/concept/s1/images/3");
  assert.equal(api.conceptImageUrl("s1", "validated"), "http://api.test/concept/s1/validated");
});

test("validateDetailedDesign posts the picture version and returns the validated design", async () => {
  const calls = [];
  const design = { details: [], latest_image_version: 6, is_validated: true };
  const api = createApi("http://api.test", async (url, init) => {
    calls.push({ url, init });
    return json(200, design);
  });

  assert.deepEqual(await api.validateDetailedDesign("s1", 6), design);

  assert.equal(calls[0].url, "http://api.test/detailed-design/s1/validate");
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), { version: 6 });
  // Without a version, the server keeps the latest picture.
  await api.validateDetailedDesign("s1");
  assert.deepEqual(JSON.parse(calls[0].init.body), { version: 6 });
  assert.deepEqual(JSON.parse(calls.at(-1).init.body), { version: null });
});

test("validateDetailedDesign explains why the server refused", async () => {
  const api = createApi("http://api.test", async () =>
    json(409, { detail: "Cannot validate yet: no piece of furniture was recorded." }),
  );

  await assert.rejects(
    api.validateDetailedDesign("s1", 6),
    (error) => error.status === 409 && /no piece of furniture/.test(error.message),
  );
});
