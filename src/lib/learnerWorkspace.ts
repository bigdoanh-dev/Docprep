import { useSyncExternalStore } from "react";
import { getActor } from "../app/identity";
import { isValidPoint } from "./launcherBounds";
export type SavedQuestion = {
  id: string;
  title: string;
  detail?: string;
  source?: string;
  note: string;
  savedAt: string;
};
export type Activity = { id: string; date: string; kind: string };
export type Workspace = {
  version: 1;
  gender: "male" | "female" | null;
  mascot: string;
  /** Legacy local fields retained for previously exported profiles; account /me is authoritative. */
  profession: string;
  specialty: string;
  organisation: string;
  remind: boolean;
  saved: SavedQuestion[];
  activity: Activity[];
  read: string[];
  reportDrafts?: {
    target_type: string;
    target_id: string;
    reason: string;
    note: string | null;
    context: { screen: string };
    created_at: string;
  }[];
  launcherPosition?: { x: number; y: number } | null;
  lastChatSearch?: string | null;
};
const EMPTY: Workspace = {
  version: 1,
  gender: null,
  mascot: "robot",
  profession: "doctor",
  specialty: "preventive",
  organisation: "",
  remind: true,
  saved: [],
  activity: [],
  read: [],
  launcherPosition: null,
  lastChatSearch: null,
};
const EVENT = "yhdp-workspace-change";
const key = () => {
  const a = getActor();
  return `yhdp.workspace.v1:${a?.mode}:${a?.id}`;
};
const snapshot = () => localStorage.getItem(key());
export function readWorkspace(): Workspace {
  try {
    const v = JSON.parse(snapshot() ?? "null");
    if (v?.version === 1) {
      const ws = { ...EMPTY, ...v };
      if (!isValidPoint(ws.launcherPosition)) {
        ws.launcherPosition = null;
      }
      if (typeof ws.lastChatSearch !== "string") {
        ws.lastChatSearch = null;
      }
      return ws;
    }
    return structuredClone(EMPTY);
  } catch {
    return structuredClone(EMPTY);
  }
}
export function updateWorkspace(change: (w: Workspace) => Workspace) {
  const current = readWorkspace();
  const next = change(current);
  const currentStr = JSON.stringify(current);
  const nextStr = JSON.stringify(next);
  if (currentStr === nextStr) return;
  localStorage.setItem(key(), nextStr);
  window.dispatchEvent(new Event(EVENT));
}
function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}
export function useWorkspace() {
  useSyncExternalStore(subscribe, snapshot);
  return readWorkspace();
}
export function clearWorkspace() {
  localStorage.removeItem(key());
  window.dispatchEvent(new Event(EVENT));
}
export const localDay = (date = new Date()) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(
    date,
  );
export function streak(days: string[], today = localDay()) {
  const unique = new Set(days);
  let date = new Date(`${today}T12:00:00+07:00`);
  if (!unique.has(today)) date.setDate(date.getDate() - 1);
  let n = 0;
  while (unique.has(localDay(date))) {
    n++;
    date.setDate(date.getDate() - 1);
  }
  return n;
}
export function recordActivity(id: string, kind: string, date = localDay()) {
  updateWorkspace((w) =>
    w.activity.some((a) => a.id === id)
      ? w
      : { ...w, activity: [...w.activity, { id, kind, date }].slice(-2000) },
  );
}
