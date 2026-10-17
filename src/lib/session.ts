// The signed-in session: the two tokens, a fetch that carries the access token, and the refresh.
//
// The server rotates the refresh token on every use and signs the device out when one is presented
// twice. So a refresh is sent by one request at a time, for everyone who is waiting, and is never
// repeated on its own. Only the server's refusal ends the session. A refresh that could not be made
// (no network, a server error) fails the requests that were waiting and leaves the tokens alone: if
// it never arrived, the next request's refresh succeeds; if it did arrive, that next one is refused
// and the session ends then, which is no worse than ending it now.
//
// No React, DOM or Vite import here: the module runs as it is under Node for its tests.

export type Tokens = { access_token: string; refresh_token: string };
export type TokenStore = {
  load(): Tokens | null;
  save(tokens: Tokens | null): void;
};

export type SessionOptions = {
  fetch: typeof fetch;
  store: TokenStore;
  /** Called once each time the session ends: signed out, or the server no longer accepts the tokens. */
  onSignedOut: () => void;
  /** Serialises refreshes across browser tabs. Default: run at once. */
  lock?: <T>(run: () => Promise<T>) => Promise<T>;
};

export type Session = {
  signedIn(): boolean;
  signIn(tokens: Tokens): void;
  signOut(): void;
  fetch(url: string, init?: RequestInit): Promise<Response>;
};

export const REFRESH_URL = "/api/v1/auth/refresh";

async function errorCode(res: Response): Promise<string | null> {
  try {
    const body = (await res.clone().json()) as {
      error?: { code?: unknown };
    } | null;
    return typeof body?.error?.code === "string" ? body.error.code : null;
  } catch {
    return null;
  }
}

type Refreshed = "ok" | "refused" | "unavailable";

export function createSession(options: SessionOptions): Session {
  const { store, onSignedOut } = options;
  const lock = options.lock ?? (<T>(run: () => Promise<T>) => run());
  let refreshing: Promise<Refreshed> | null = null;

  const end = () => {
    if (store.load() === null) return;
    store.save(null);
    onSignedOut();
  };

  const send = (
    url: string,
    init: RequestInit | undefined,
    tokens: Tokens | null,
  ) => {
    const headers = new Headers(init?.headers);
    if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);
    return options.fetch(url, { ...init, headers });
  };

  // 'ok' when the store holds tokens newer than `usedAccess`, whether this call fetched them or
  // another request or tab already had.
  const refresh = (usedAccess: string): Promise<Refreshed> => {
    refreshing ??= lock(async (): Promise<Refreshed> => {
      const current = store.load(); // read inside the lock: another tab may just have refreshed
      if (current === null) return "refused";
      if (current.access_token !== usedAccess) return "ok";
      try {
        const res = await options.fetch(REFRESH_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: current.refresh_token }),
        });
        if (res.status >= 500) return "unavailable";
        if (!res.ok) return "refused";
        const pair = (await res.json()) as Tokens;
        store.save({
          access_token: pair.access_token,
          refresh_token: pair.refresh_token,
        });
        return "ok";
      } catch {
        return "unavailable";
      }
    }).finally(() => {
      refreshing = null;
    });
    return refreshing;
  };

  return {
    signedIn: () => store.load() !== null,
    signIn: (tokens) =>
      store.save({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
      }),
    signOut: end,
    async fetch(url, init) {
      const tokens = store.load();
      const res = await send(url, init, tokens);
      if (res.status !== 401 || tokens === null) return res;
      const refreshed =
        (await errorCode(res)) === "token_expired"
          ? await refresh(tokens.access_token)
          : "refused";
      if (refreshed === "unavailable")
        throw new TypeError(
          "The session could not be refreshed: the server was not reached.",
        );
      if (refreshed === "refused") {
        end();
        return res;
      }
      // Once only: whatever this answers is the caller's answer.
      return send(url, init, store.load());
    },
  };
}
