// Reading server-sent events from a fetch body. No import here: the module runs as it is under Node
// for its tests.

export const STREAM_BROKEN =
  "Mất kết nối với máy chủ giữa chừng. Vui lòng thử lại.";

type Reader = { read(): Promise<{ value?: Uint8Array; done: boolean }> };

/** Hands each event to `onEvent` as it arrives. A connection that drops half-way rejects with
 *  STREAM_BROKEN, after the events that did arrive; the browser's own (English) message is not shown. */
export async function readEvents(
  reader: Reader,
  onEvent: (event: string, data: any) => void,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (block: string) => {
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7).trim();
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (data) onEvent(event, JSON.parse(data));
  };
  for (;;) {
    let chunk: { value?: Uint8Array; done: boolean };
    try {
      chunk = await reader.read();
    } catch {
      throw new Error(STREAM_BROKEN);
    }
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    let cut = buffer.indexOf("\n\n");
    while (cut !== -1) {
      flush(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      cut = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) flush(buffer);
}
