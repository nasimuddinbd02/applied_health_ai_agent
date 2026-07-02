// Frontend unit test (Node built-in test runner; Node strips the TS types).
import assert from "node:assert/strict";
import test from "node:test";

import { Formatter } from "../lib/format.ts";

test("Formatter.usd uses 4 decimal places by default", () => {
  assert.equal(Formatter.usd(0.12345), "$0.1235");
});

test("Formatter.usd respects a custom precision", () => {
  assert.equal(Formatter.usd(0.1, 2), "$0.10");
});

test("Formatter.usd coerces and formats integers", () => {
  assert.equal(Formatter.usd(5), "$5.0000");
});
