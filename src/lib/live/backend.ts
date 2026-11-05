// The repo's own FastAPI backend (/api/v1/*), reached through the learner session. Its errors come as
// FastAPI's {"detail": "..."} in English; they become a LiveError with a Vietnamese message here,
// which api.ts turns into the ApiError the screens read.
import { session } from "../client";

export class LiveError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const fail = (status: number, code: string, message: string): never => {
  throw new LiveError(status, code, message);
};

const NETWORK = "Không kết nối được máy chủ. Vui lòng thử lại.";

const BY_STATUS: Record<number, [string, string]> = {
  400: ["bad_request", "Yêu cầu không hợp lệ."],
  401: [
    "unauthenticated",
    "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
  ],
  403: ["forbidden", "Tài khoản này không có quyền thực hiện thao tác này."],
  404: ["not_found", "Không tìm thấy dữ liệu yêu cầu."],
  422: [
    "invalid_request",
    "Máy chủ không nhận yêu cầu này. Vui lòng thử lại hoặc tải lại trang.",
  ],
  429: ["rate_limited", "Thử quá nhiều lần. Vui lòng đợi 15 phút rồi thử lại."],
};

function errorFor(status: number): LiveError {
  const [code, message] = BY_STATUS[status] ?? [
    "server_error",
    "Máy chủ gặp lỗi. Vui lòng thử lại.",
  ];
  return new LiveError(status, code, message);
}

/** The raw response, for the chat stream; any other status than 2xx is thrown. */
export async function backendFetch(
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await session.fetch(`/api/v1${path}`, init);
  } catch {
    throw new LiveError(0, "network", NETWORK);
  }
  if (!res.ok) throw errorFor(res.status);
  return res;
}

export const backend = async <T = any>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> => (await backendFetch(method, path, body)).json();

export const get = <T = any>(path: string) => backend<T>("GET", path);
export const post = <T = any>(path: string, body: unknown = {}) =>
  backend<T>("POST", path, body);

/** Username and password sign-in; the only request sent without a token. */
export async function liveLogin(
  username: string,
  password: string,
): Promise<{ token: string; username: string; role: string }> {
  let res: Response;
  try {
    res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new LiveError(0, "network", NETWORK);
  }
  if (res.status === 401)
    throw new LiveError(
      401,
      "wrong_credentials",
      "Sai tên đăng nhập hoặc mật khẩu.",
    );
  if (!res.ok) throw errorFor(res.status);
  return res.json();
}
