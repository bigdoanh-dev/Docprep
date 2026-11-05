// Opening the tutor popup from another screen (Home): on a past conversation, or on a new one that
// starts with a question. The shell owns the popup and listens for this.
//
// No React import here: a window event, so any screen can ask without a shared provider.

export type TutorRequest = { session?: number; ask?: string; key: number };

const EVENT = "yhdp-open-tutor";

export function openTutor(request: Omit<TutorRequest, "key">) {
  window.dispatchEvent(
    new CustomEvent(EVENT, { detail: { ...request, key: Date.now() } }),
  );
}

export function onOpenTutor(listener: (request: TutorRequest) => void) {
  const handle = (e: Event) =>
    listener((e as CustomEvent<TutorRequest>).detail);
  window.addEventListener(EVENT, handle);
  return () => window.removeEventListener(EVENT, handle);
}
