// The app's one session: tokens in localStorage, and who to tell when it ends or consent is needed.
import { setActor } from "../app/identity";
import { createSession, type Tokens } from "./session";

export const STORAGE_KEY = "yhdp.session";
// A staff member (Quản lý cấp Bộ) signs in apart from the learner: a learner session is never reused.
export const STAFF_STORAGE_KEY = "yhdp.staff";

type Listener = () => void;
const signedOutListeners = new Set<Listener>();
const staffSignedOutListeners = new Set<Listener>();
const consentListeners = new Set<Listener>();
const tell = (listeners: Set<Listener>) =>
  [...listeners].forEach((listener) => listener());

function subscribe(listeners: Set<Listener>, listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// Only the two tokens are kept in the browser; nothing else about the person.
const storeAt = (key: string) => ({
  load(): Tokens | null {
    try {
      const saved = JSON.parse(localStorage.getItem(key) ?? "null");
      return typeof saved?.access_token === "string" &&
        typeof saved?.refresh_token === "string"
        ? saved
        : null;
    } catch {
      return null;
    }
  },
  save(tokens: Tokens | null) {
    if (tokens === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(tokens));
  },
});

export const session = createSession({
  fetch: (input, init) => fetch(input, init),
  store: storeAt(STORAGE_KEY),
  onSignedOut: () => {
    tell(signedOutListeners);
    setActor(null);
  },
  // Two tabs share the tokens: only one of them may refresh at a time. Web Locks exist on HTTPS and
  // localhost; without them (a phone on plain HTTP) two tabs refreshing in the same instant can
  // sign the device out.
  lock:
    "locks" in navigator
      ? (run) => navigator.locks.request("yhdp.refresh", run)
      : undefined,
});

export const staffSession = createSession({
  fetch: (input, init) => fetch(input, init),
  store: storeAt(STAFF_STORAGE_KEY),
  onSignedOut: () => {
    tell(staffSignedOutListeners);
    setActor(null);
  },
  lock:
    "locks" in navigator
      ? (run) => navigator.locks.request("yhdp.staff.refresh", run)
      : undefined,
});

/** The session ended: signed out here or in another tab, or the server no longer accepts the tokens. */
export const onSignedOut = (listener: Listener) =>
  subscribe(signedOutListeners, listener);
/** A request was refused until the learner gives the current service consent. */
export const onConsentRequired = (listener: Listener) =>
  subscribe(consentListeners, listener);
export const notifyConsentRequired = () => tell(consentListeners);
/** The staff session ended. */
export const onStaffSignedOut = (listener: Listener) =>
  subscribe(staffSignedOutListeners, listener);

// Signing out in one tab signs the others out.
window.addEventListener("storage", (event) => {
  if (event.key === STORAGE_KEY && event.newValue === null)
    tell(signedOutListeners);
  if (event.key === STAFF_STORAGE_KEY && event.newValue === null)
    tell(staffSignedOutListeners);
});
