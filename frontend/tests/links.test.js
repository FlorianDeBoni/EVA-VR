import assert from "node:assert/strict";
import { test } from "node:test";

import { sessionFromSearch, vrPageUrl } from "../src/links.js";

test("the VR page url carries the session, escaped", () => {
  assert.equal(vrPageUrl("abc-123"), "/vr.html?session=abc-123");
  assert.equal(vrPageUrl("a b&c"), "/vr.html?session=a%20b%26c");
});

test("the session is read back from the url of the VR page", () => {
  assert.equal(sessionFromSearch(new URL(`http://x${vrPageUrl("a b&c")}`).search), "a b&c");
  assert.equal(sessionFromSearch("?session=abc-123"), "abc-123");
  assert.equal(sessionFromSearch(""), null);
  assert.equal(sessionFromSearch("?other=1"), null);
});
