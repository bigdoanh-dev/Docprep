// Idempotency keys. Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { newKey } from "../src/lib/keys.ts";

test("every key is different", () => {
  const keys = new Set(Array.from({ length: 200 }, () => newKey()));
  assert.equal(keys.size, 200);
});

test("a key can be made where crypto.randomUUID does not exist (a phone on plain HTTP)", () => {
  const insecure = {
    getRandomValues: (array: Uint8Array) => {
      array.set(crypto.getRandomValues(new Uint8Array(array.byteLength)));
      return array;
    },
  };
  const a = newKey(insecure);
  const b = newKey(insecure);
  assert.match(a, /^[0-9a-f]{32}$/);
  assert.notEqual(a, b);
});
