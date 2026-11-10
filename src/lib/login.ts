import type { TokenPair } from "./api";

export type UsernameLoginResult = TokenPair;

/** Unified Phase 1 sign-in, preserving the server role and rotating token pair. */
export async function usernameLogin(
  username: string,
  password: string,
  fetcher: typeof fetch = fetch,
): Promise<UsernameLoginResult> {
  let response: Response;
  try {
    response = await fetcher("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.trim(), password }),
    });
  } catch {
    throw new Error("Không kết nối được máy chủ. Vui lòng thử lại.");
  }
  if (response.status === 401)
    throw new Error("Sai tên đăng nhập hoặc mật khẩu.");
  if (response.status === 429)
    throw new Error("Thử quá nhiều lần. Vui lòng đợi rồi thử lại.");
  if (!response.ok) throw new Error("Không thể đăng nhập. Vui lòng thử lại.");
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error("Phản hồi đăng nhập không hợp lệ. Vui lòng thử lại.");
  }
  const result = data as Partial<UsernameLoginResult> | null;
  if (
    !result ||
    typeof result.access_token !== "string" ||
    !result.access_token.trim() ||
    typeof result.refresh_token !== "string" ||
    !result.refresh_token.trim() ||
    typeof result.expires_in !== "number" ||
    !Number.isFinite(result.expires_in) ||
    result.expires_in <= 0 ||
    typeof result.consent_required !== "boolean" ||
    typeof result.role !== "string" ||
    !result.role.trim()
  ) {
    throw new Error("Phản hồi đăng nhập không hợp lệ. Vui lòng thử lại.");
  }
  return result as UsernameLoginResult;
}
