import { useSyncExternalStore } from "react";
export type Role =
  "learner" | "reviewer" | "lecturer" | "admin" | "ministry_viewer";
export type Actor = {
  role: Role;
  mode: "demo" | "live";
  name: string;
  id: string;
};
const KEY = "yhdp.actor.v1",
  EVENT = "yhdp-identity";
export const roleNames: Record<Role, string> = {
  learner: "Người học",
  reviewer: "Chuyên gia thẩm định",
  lecturer: "Giảng viên",
  admin: "Quản trị viên",
  ministry_viewer: "Cán bộ quản lý",
};
const raw = () => localStorage.getItem(KEY);
export function getActor(): Actor | null {
  try {
    return JSON.parse(raw() ?? "null");
  } catch {
    return null;
  }
}
export function setActor(actor: Actor | null) {
  if (actor) localStorage.setItem(KEY, JSON.stringify(actor));
  else localStorage.removeItem(KEY);
  window.dispatchEvent(new Event(EVENT));
}
function subscribe(listener: () => void) {
  window.addEventListener(EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}
export function useActor(): Actor | null {
  const value = useSyncExternalStore(subscribe, raw);
  try {
    return JSON.parse(value ?? "null");
  } catch {
    return null;
  }
}
export const roleHome = (role: Role) =>
  role === "learner"
    ? "/"
    : role === "reviewer"
      ? "/tham-dinh"
      : role === "lecturer"
        ? "/giang-vien"
        : role === "admin"
          ? "/quan-tri"
          : "/quan-ly";
