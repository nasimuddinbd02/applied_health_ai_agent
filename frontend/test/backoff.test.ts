// Reconnect pacing (Node built-in test runner; Node strips the TS types).
import assert from "node:assert/strict";
import test from "node:test";

import { BASE_BACKOFF_MS, MAX_BACKOFF_MS, backoffCeiling, reconnectDelay } from "../src/lib/backoff.ts";

test("the first retry is quick", () => {
  assert.equal(backoffCeiling(0), BASE_BACKOFF_MS);
});

test("the ceiling doubles per attempt", () => {
  assert.equal(backoffCeiling(1), 1000);
  assert.equal(backoffCeiling(3), 4000);
});

test("the ceiling is capped so a long outage does not park clients forever", () => {
  assert.equal(backoffCeiling(20), MAX_BACKOFF_MS);
  assert.equal(backoffCeiling(1e9), MAX_BACKOFF_MS);
});

test("delays are jittered across the whole window, not clustered", () => {
  assert.equal(reconnectDelay(3, () => 0), 0);
  assert.equal(reconnectDelay(3, () => 0.5), 2000);
  assert.equal(reconnectDelay(3, () => 1), 4000);
});
