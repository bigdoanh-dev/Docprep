import { getActor } from "../app/identity";
import { ApiError, toApiError } from "./api";
import { session } from "./client";
import { demoStream } from "./demo/store";
import { readEvents } from "./sseRead";

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
  let res: Response;
  try {
    res = await session.fetch(`/api/v1${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
  } catch {
    throw new ApiError(
      0,
      "network",
      "Không kết nối được máy chủ. Vui lòng thử lại.",
    );
  }
  if (!res.ok || !res.body) throw await toApiError(res);
  try {
    await readEvents(res.body.getReader(), onEvent);
  } catch (e) {
    throw e instanceof ApiError
      ? e
      : new ApiError(0, "network", (e as Error).message);
  }
}
