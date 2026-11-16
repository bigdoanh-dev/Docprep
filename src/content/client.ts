export type Session = {
  access_token: string;
  refresh_token: string;
  roles: string[];
  display_name: string;
};
const KEY = "content.session.v1";
export function session(): Session | null {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "null");
  } catch {
    return null;
  }
}
export function saveSession(value: Session | null) {
  if (value) sessionStorage.setItem(KEY, JSON.stringify(value));
  else sessionStorage.removeItem(KEY);
}
let refreshing: Promise<void> | null = null;
export async function api<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const current = session();
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (current) headers.set("Authorization", `Bearer ${current.access_token}`);
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (
    response.status === 401 &&
    retry &&
    current &&
    !path.startsWith("/auth/")
  ) {
    refreshing ??= (async () => {
      try {
        saveSession(
          await api<Session>(
            "/auth/refresh",
            {
              method: "POST",
              body: JSON.stringify({ refresh_token: current.refresh_token }),
            },
            false,
          ),
        );
      } catch (error) {
        saveSession(null);
        window.dispatchEvent(new Event("content-auth-expired"));
        throw error;
      }
    })().finally(() => {
      refreshing = null;
    });
    await refreshing;
    return api<T>(path, init, false);
  }
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error?.message_vi || `Lỗi ${response.status}`);
  return data as T;
}
export function write<T>(path: string, body: unknown, key: string) {
  return api<T>(path, {
    method: "POST",
    headers: { "Idempotency-Key": key },
    body: JSON.stringify(body),
  });
}
export function download(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
