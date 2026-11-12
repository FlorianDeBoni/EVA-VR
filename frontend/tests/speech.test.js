import assert from "node:assert/strict";
import { test } from "node:test";

import { hasSpeech } from "../src/speech.js";

const limits = { minMs: 500, minLevel: 0.01 };

test("a long enough and loud enough recording is sent", () => {
  assert.equal(hasSpeech({ peak: 0.2, durationMs: 3000 }, limits), true);
  assert.equal(hasSpeech({ peak: 0.01, durationMs: 500 }, limits), true);
});

test("a silent recording is not sent", () => {
  assert.equal(hasSpeech({ peak: 0, durationMs: 3000 }, limits), false);
  assert.equal(hasSpeech({ peak: 0.004, durationMs: 3000 }, limits), false);
});

test("a recording that is too short is not sent", () => {
  assert.equal(hasSpeech({ peak: 0.5, durationMs: 120 }, limits), false);
});
