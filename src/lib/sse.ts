import { getActor } from "../app/identity";
import { ApiError, toApiError } from "./api";
import { session } from "./client";
import { demoStream } from "./demo/store";
import { readEvents, STREAM_BROKEN } from "./sseRead";
import { minimiseText } from "./privacy";

type Listener = (event: string, data: any) => void;
type Pending = { path: string; key: string; body: unknown; turnId?: string; cursor?: string };
export type TurnSnapshot = {
  turn_id: string; kind: string; session_id: number | null; turn_status: string;
  result: { answer: any; final: any } | null; error: { code: string; message_vi: string } | null;
};
const storageKey = () => `docprep:pending-ai:${getActor()?.id ?? "anonymous"}`;
const save = (value: Pending | null) => {
  try {
    if (value) sessionStorage.setItem(storageKey(), JSON.stringify(value));
    else sessionStorage.removeItem(storageKey());
  } catch { /* Server discovery also works without storage. */ }
};
const pending = (): Pending | null => {
  try { return JSON.parse(sessionStorage.getItem(storageKey()) ?? "null"); }
  catch { return null; }
};
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function snapshot(id: string): Promise<TurnSnapshot> {
  const res = await session.fetch(`/api/v1/chat/turns/${encodeURIComponent(id)}`);
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

async function consume(res: Response, saved: Pending, onEvent: Listener): Promise<boolean> {
  if (!res.ok || !res.body) throw await toApiError(res);
  saved.turnId = res.headers.get("X-Turn-ID") ?? saved.turnId;
  save(saved);
  let final = false;
  const reader = res.body.getReader();
  try {
    await readEvents(reader, (event, data, id) => {
      if (id) { saved.cursor = id; save(saved); }
      if (event === "final") { final = true; save(null); }
      onEvent(event, data);
      if (event === "final" && data.error)
        throw new ApiError(503, data.error.code, data.error.message_vi);
    });
  } finally { reader.releaseLock(); }
  return final;
}

export async function resumeTurn(id: string, onEvent: Listener, signal?: AbortSignal): Promise<void> {
  const saved: Pending = pending()?.turnId === id ? pending()! : { path: "", key: "", body: {}, turnId: id };
  for (let attempt = 0; attempt < 4; attempt++) {
    if (signal?.aborted) return;
    try {
      const headers: Record<string, string> = {};
      if (saved.cursor) headers["Last-Event-ID"] = saved.cursor;
      const res = await session.fetch(`/api/v1/chat/turns/${id}/events`, { headers, signal });
      if (res.status === 410) {
        const current = await snapshot(id);
        saved.cursor = undefined;
        if (current.result) {
          onEvent("answer", current.result.answer); onEvent("final", current.result.final); save(null); return;
        }
        if (!["queued", "running"].includes(current.turn_status)) {
          save(null); throw new ApiError(503, current.error?.code ?? "ai_failed", current.error?.message_vi ?? STREAM_BROKEN);
        }
        save(saved);
        continue;
      }
      if (await consume(res, saved, onEvent)) return;
    } catch (error) {
      if (signal?.aborted) return;
      if (error instanceof ApiError && error.status > 0 && error.status !== 502 && error.status !== 504 && error.code !== "ai_unavailable") throw error;
      if (attempt === 3) throw error;
    }
    await pause(500 * (attempt + 1));
  }
  throw new ApiError(0, "network", STREAM_BROKEN);
}

export async function activeSessionTurn(sessionId: number): Promise<TurnSnapshot | null> {
  if (getActor()?.mode === "demo") return null;
  const res = await session.fetch("/api/v1/chat/turns/active");
  if (res.status === 404) return null; // Alpha compatibility
  if (!res.ok) throw await toApiError(res);
  const { item } = await res.json() as { item: TurnSnapshot | null };
  return item?.kind === "chat" && item.session_id === sessionId ? item : null;
}

export async function cancelTurn(id: string): Promise<void> {
  const res = await session.fetch(`/api/v1/chat/turns/${id}`, { method: "DELETE" });
  if (!res.ok) throw await toApiError(res);
  save(null);
}

// EventSource only does GET, so the POST streams (chat, tutor) are read from the fetch body.
export async function postSSE(
  path: string,
  body: unknown,
  onEvent: (event: string, data: any) => void,
): Promise<void> {
  if (getActor()?.mode === "demo") {
    await demoStream(path, body, onEvent);
    return;
  }
  const safeBody = body && typeof body === "object" && "text" in body
    ? { ...body, text: minimiseText(String(body.text)) } : body;
  const old = pending();
  const saved: Pending = old?.path === path && JSON.stringify(old.body) === JSON.stringify(safeBody)
    ? old : { path, key: crypto.randomUUID(), body: safeBody };
  save(saved);
  if (saved.turnId) return resumeTurn(saved.turnId, onEvent);
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await session.fetch(`/api/v1${path}`, {
        method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": saved.key },
        body: JSON.stringify(safeBody ?? {}),
      });
      if (await consume(res, saved, onEvent)) return;
      if (saved.turnId) return resumeTurn(saved.turnId, onEvent);
      throw new ApiError(0, "network", STREAM_BROKEN);
    } catch (error) {
      if (error instanceof ApiError && error.status > 0) throw error;
      if (saved.turnId) return resumeTurn(saved.turnId, onEvent);
      if (attempt === 2) throw new ApiError(0, "network", STREAM_BROKEN);
      await pause(500 * (attempt + 1));
    }
  }
}
