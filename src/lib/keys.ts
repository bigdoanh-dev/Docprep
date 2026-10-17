// Idempotency keys: one per thing the learner means to do. Sending the same key again (a retry
// after a lost answer) makes the server return what it stored instead of doing the thing twice.

type RandomSource = {
  getRandomValues(array: Uint8Array): Uint8Array;
  randomUUID?: () => string;
};

/** A new random key. `crypto.randomUUID` exists only on HTTPS and localhost; a phone that opens the
 * dev server by its address has `getRandomValues` alone, which is as random. */
export function newKey(
  source: RandomSource = globalThis.crypto as unknown as RandomSource,
): string {
  if (typeof source.randomUUID === "function") return source.randomUUID();
  const bytes = source.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
