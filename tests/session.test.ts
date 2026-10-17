// The session module: tokens, the authorised fetch and the single-flight refresh.
// Run with `npm test` (Node's own test runner; no browser, no backend).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  REFRESH_URL,
  createSession,
  type TokenStore,
  type Tokens,
} from "../src/lib/session.ts";

type Call = {
  url: string;
  method: string;
  authorization: string | null;
  headers: Record<string, string>;
  body: string | null;
};
type Reply = Response | Error | ((call: Call) => Response | Promise<Response>);

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const expired = () =>
  json(401, {
    error: {
      code: "token_expired",
      message_vi: "Phiên đăng nhập đã hết hạn.",
      details: null,
    },
  });
const unauthenticated = () =>
  json(401, {
    error: {
      code: "unauthenticated",
      message_vi: "Bạn cần đăng nhập.",
      details: null,
    },
  });
const pair = (n: number): Tokens => ({
  access_token: `a${n}`,
  refresh_token: `r${n}`,
});
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

// A fake server: `route(call)` picks the reply; every call is recorded.
function server(route: (call: Call) => Reply) {
  const calls: Call[] = [];
  const fetchFn = (async (
    input: string | URL | Request,
    init?: RequestInit,
  ) => {
    const headers = Object.fromEntries(new Headers(init?.headers).entries());
    const call: Call = {
      url: String(input),
      method: init?.method ?? "GET",
      authorization: headers.authorization ?? null,
      headers,
      body: typeof init?.body === "string" ? init.body : null,
    };
    calls.push(call);
    const reply = route(call);
    if (reply instanceof Error) throw reply;
    return typeof reply === "function" ? reply(call) : reply;
  }) as typeof fetch;
  return {
    calls,
    fetchFn,
    refreshes: () => calls.filter((c) => c.url === REFRESH_URL),
  };
}

function memoryStore(
  initial: Tokens | null,
): TokenStore & { tokens: Tokens | null } {
  return {
    tokens: initial,
    load() {
      return this.tokens;
    },
    save(tokens) {
      this.tokens = tokens;
    },
  };
}

// The usual server: a1 has expired, r1 buys a2/r2, a2 is good.
function expiring(extra?: (call: Call) => Reply | undefined) {
  return server((call) => {
    const special = extra?.(call);
    if (special !== undefined) return special;
    if (call.url === REFRESH_URL)
      return json(200, {
        ...pair(2),
        expires_in: 1800,
        role: "learner",
        consent_required: false,
      });
    return call.authorization === "Bearer a2"
      ? json(200, { ok: true })
      : expired();
  });
}

function setup(
  route: ReturnType<typeof server>,
  tokens: Tokens | null = pair(1),
) {
  const store = memoryStore(tokens);
  let signedOut = 0;
  const session = createSession({
    fetch: route.fetchFn,
    store,
    onSignedOut: () => {
      signedOut += 1;
    },
  });
  return { session, store, signedOutCount: () => signedOut };
}

test("adds the bearer token and returns the response untouched", async () => {
  const reply = json(200, { ok: true });
  const s = server(() => reply);
  const { session } = setup(s);
  const res = await session.fetch("/api/v1/home");
  assert.equal(s.calls.length, 1);
  assert.equal(s.calls[0].authorization, "Bearer a1");
  assert.equal(res, reply);
  assert.equal(res.bodyUsed, false);
});

test("sends no Authorization header when signed out", async () => {
  const s = server(() => json(200, { ok: true }));
  const { session, signedOutCount } = setup(s, null);
  await session.fetch("/api/v1/auth/activate", { method: "POST", body: "{}" });
  assert.equal(s.calls[0].authorization, null);
  assert.equal(session.signedIn(), false);
  assert.equal(signedOutCount(), 0);
});

test("refreshes once on token_expired and retries with the new token", async () => {
  const s = expiring();
  const { session, store } = setup(s);
  const res = await session.fetch("/api/v1/home");
  assert.deepEqual(
    s.calls.map((c) => [c.method, c.url, c.authorization]),
    [
      ["GET", "/api/v1/home", "Bearer a1"],
      ["POST", REFRESH_URL, null],
      ["GET", "/api/v1/home", "Bearer a2"],
    ],
  );
  assert.equal(s.calls[1].body, JSON.stringify({ refresh_token: "r1" }));
  assert.deepEqual(store.tokens, pair(2));
  assert.equal(res.status, 200);
});

test("three requests that expire together cause one refresh", async () => {
  const s = expiring();
  const { session } = setup(s);
  const results = await Promise.all(
    ["/a", "/b", "/c"].map((p) => session.fetch(`/api/v1${p}`)),
  );
  assert.deepEqual(
    results.map((r) => r.status),
    [200, 200, 200],
  );
  assert.equal(s.refreshes().length, 1);
  assert.equal(
    s.calls.filter((c) => c.authorization === "Bearer a2").length,
    3,
  );
});

test("a retried autosave keeps its method, headers and body", async () => {
  const s = expiring();
  const { session } = setup(s);
  const body = JSON.stringify({ chosen: "b", flagged: true });
  await session.fetch("/api/v1/attempts/7/answers/q-1", {
    method: "PUT",
    headers: { "Content-Type": "application/json", "Idempotency-Key": "k-1" },
    body,
  });
  const retried = s.calls[2];
  assert.equal(retried.method, "PUT");
  assert.equal(retried.body, body);
  assert.equal(retried.headers["content-type"], "application/json");
  assert.equal(retried.headers["idempotency-key"], "k-1");
  assert.equal(retried.authorization, "Bearer a2");
});

test("a request that already has an outdated token does not refresh again", async () => {
  let store: ReturnType<typeof memoryStore>;
  const s = expiring((call) => {
    if (call.authorization === "Bearer a1") {
      store.tokens = pair(2); // another tab refreshed while this request was on its way
      return expired();
    }
    return undefined;
  });
  const made = setup(s);
  store = made.store;
  const res = await made.session.fetch("/api/v1/home");
  assert.equal(res.status, 200);
  assert.equal(s.refreshes().length, 0);
  assert.equal(s.calls[1].authorization, "Bearer a2");
});

test("a refused refresh ends the session once", async () => {
  const s = server((call) =>
    call.url === REFRESH_URL ? unauthenticated() : expired(),
  );
  const { session, store, signedOutCount } = setup(s);
  const results = await Promise.all([
    session.fetch("/api/v1/a"),
    session.fetch("/api/v1/b"),
  ]);
  assert.deepEqual(
    results.map((r) => r.status),
    [401, 401],
  );
  assert.equal(s.refreshes().length, 1);
  assert.equal(store.tokens, null);
  assert.equal(session.signedIn(), false);
  assert.equal(signedOutCount(), 1);
});

test("a refresh that fails on the network keeps the session and fails that request", async () => {
  let online = false;
  const s = expiring((call) =>
    call.url === REFRESH_URL && !online
      ? new TypeError("network down")
      : undefined,
  );
  const { session, store, signedOutCount } = setup(s);
  await assert.rejects(
    session.fetch("/api/v1/attempts/7/answers/q-1", {
      method: "PUT",
      body: "{}",
    }),
  );
  assert.equal(s.refreshes().length, 1); // not retried by itself
  assert.deepEqual(store.tokens, pair(1)); // the tokens may still be good: the refresh may never have arrived
  assert.equal(signedOutCount(), 0);
  online = true;
  const res = await session.fetch("/api/v1/attempts/7/answers/q-1", {
    method: "PUT",
    body: "{}",
  });
  assert.equal(res.status, 200); // the next request refreshes and goes through
  assert.deepEqual(store.tokens, pair(2));
});

test("a refresh answered with a server error keeps the session", async () => {
  const s = server((call) =>
    call.url === REFRESH_URL
      ? json(502, { error: { code: "bad_gateway" } })
      : expired(),
  );
  const { session, store, signedOutCount } = setup(s);
  await assert.rejects(session.fetch("/api/v1/home"));
  assert.deepEqual(store.tokens, pair(1));
  assert.equal(signedOutCount(), 0);
});

test("two tabs that expire together send one refresh between them", async () => {
  // Two sessions (tabs) over one store (localStorage) and one lock (Web Locks). The server follows
  // the real rule: a refresh token works once, and presenting it twice would sign the device out.
  let used = 0;
  const s = server((call) => {
    if (call.url === REFRESH_URL) {
      used += 1;
      return used === 1
        ? json(200, {
            ...pair(2),
            expires_in: 1800,
            role: "learner",
            consent_required: false,
          })
        : unauthenticated();
    }
    return call.authorization === "Bearer a2"
      ? json(200, { ok: true })
      : expired();
  });
  const store = memoryStore(pair(1));
  let queue: Promise<unknown> = Promise.resolve();
  const lock = <T>(run: () => Promise<T>): Promise<T> => {
    const next = queue.then(run);
    queue = next.catch(() => undefined);
    return next;
  };
  let signedOut = 0;
  const tab = () =>
    createSession({
      fetch: s.fetchFn,
      store,
      lock,
      onSignedOut: () => {
        signedOut += 1;
      },
    });
  const results = await Promise.all([
    tab().fetch("/api/v1/home"),
    tab().fetch("/api/v1/exams"),
  ]);
  assert.deepEqual(
    results.map((r) => r.status),
    [200, 200],
  );
  assert.equal(s.refreshes().length, 1);
  assert.equal(signedOut, 0);
});

test("unauthenticated ends the session without a refresh", async () => {
  const s = server(() => unauthenticated());
  const { session, store, signedOutCount } = setup(s);
  const res = await session.fetch("/api/v1/home");
  assert.equal(res.status, 401);
  assert.equal(s.refreshes().length, 0);
  assert.equal(store.tokens, null);
  assert.equal(signedOutCount(), 1);
});

test("a retry that is refused again is returned, not retried", async () => {
  const s = server((call) =>
    call.url === REFRESH_URL
      ? json(200, {
          ...pair(2),
          expires_in: 1800,
          role: "learner",
          consent_required: false,
        })
      : expired(),
  );
  const { session } = setup(s);
  const res = await session.fetch("/api/v1/home");
  assert.equal(res.status, 401);
  assert.equal(s.calls.length, 3);
  assert.equal(s.refreshes().length, 1);
});

test("a 401 that is not JSON ends the session", async () => {
  const s = server(
    () => new Response("<html>Unauthorized</html>", { status: 401 }),
  );
  const { session, store, signedOutCount } = setup(s);
  const res = await session.fetch("/api/v1/home");
  assert.equal(res.status, 401);
  assert.equal(store.tokens, null);
  assert.equal(signedOutCount(), 1);
});

test("signOut forgets the tokens and reports it", async () => {
  const s = server(() => json(200, { ok: true }));
  const { session, store, signedOutCount } = setup(s);
  assert.equal(session.signedIn(), true);
  session.signOut();
  await tick();
  assert.equal(store.tokens, null);
  assert.equal(session.signedIn(), false);
  assert.equal(signedOutCount(), 1);
  session.signIn(pair(5));
  assert.deepEqual(store.tokens, pair(5));
  assert.equal(session.signedIn(), true);
});
