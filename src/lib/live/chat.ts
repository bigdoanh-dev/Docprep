// Hỏi đáp in live mode. The backend answers one question at a time (POST /api/v1/chat, NDJSON) and
// keeps no conversations, so the sessions and their messages are kept on the device and the recent
// turns sent with each question. Its events become the ones the screens read:
//   plan    → step "plan": the chapters a broad question is gathered from
//   sources → steps "search"/"write" and the citations     delta → "answer" with the text so far
//   tool    → a practice set offered, or the card added     done  → "final"
import type { ChatSuggestion, Citation, StepEvent } from "../chatTurn";
import { backendFetch, fail, get, LiveError } from "./backend";
import { cites, rememberSources, stemOf } from "./shapes";
import {
  liveTransaction,
  nextId,
  readLive,
  record,
  type LiveState,
} from "./store";

const HISTORY = 4; // as many turns as the backend reads (MAX_HISTORY in yhdp/api/chat.py)
// ChatRequest's limits: a longer question or context list is refused with 422.
const MAX_QUESTION = 2000;
const MAX_CONTEXT = 10;
const NEW_TITLE = "Cuộc trò chuyện mới";
// The "write" step, in the words of the move being made.
const WRITE_STEP: Record<string, string> = {
  giai_thich: "Soạn câu trả lời có trích dẫn",
  auto: "Soạn câu trả lời có trích dẫn",
  so_sanh: "Lập bảng so sánh có trích dẫn",
  vi_du: "Dựng ca lâm sàng minh họa",
  kiem_tra: "Soạn câu hỏi kiểm tra",
  cham: "Chấm câu trả lời theo tài liệu",
  tom_tat: "Tóm tắt ý chính để ôn",
};
const EXPLAIN =
  "Giải thích vì sao đáp án đúng là đúng và vì sao từng phương án còn lại sai, dựa trên nguồn.";

const message = (fields: Record<string, unknown>) => ({
  created_at: new Date().toISOString(),
  state: null,
  format: "text",
  citations: [],
  notice: null,
  trace_summary: null,
  clarify_options: [],
  searched: [],
  nearest_chapter: null,
  suggestions: [],
  helpful: null,
  trace: [],
  ...fields,
});

// What the model is told about the quiz question a conversation is about.
function aboutQuestion(s: LiveState, questionId: string) {
  const q = s.questions[questionId];
  if (!q) return null;
  const options = Object.entries(q.options)
    .map(([k, v]) => `${k}. ${v}`)
    .join("\n");
  return {
    context: q.sources,
    text: `Câu hỏi trắc nghiệm:\n${q.stem}\n${options}\nĐáp án đúng: ${q.answer}.`,
  };
}

/** The chat routes that are plain requests; undefined for any other path. */
export async function liveChatCall(method: string, p: string, body: any) {
  let m: RegExpExecArray | null;
  if (p === "/chat/sessions" && method === "POST") {
    const questionId = body.question_id ? String(body.question_id) : null;
    return liveTransaction((s) => {
      if (questionId && !s.questions[questionId])
        fail(409, "not_answered", "Hãy trả lời câu trước khi hỏi gia sư.");
      const id = nextId(s);
      s.chats.unshift({
        id,
        title: questionId
          ? `Về câu: ${s.questions[questionId].stem.slice(0, 60)}`
          : NEW_TITLE,
        question_id: questionId,
        updated_at: new Date().toISOString(),
        messages: [],
      });
      return { id };
    });
  }
  if (p === "/chat/sessions") {
    const chats = [...readLive().chats].sort((a, b) =>
      b.updated_at.localeCompare(a.updated_at),
    );
    return {
      items: chats.map(({ id, title, updated_at }) => ({
        id,
        title,
        updated_at,
      })),
      next_cursor: null,
    };
  }
  if ((m = /^\/chat\/sessions\/(\d+)\/messages$/.exec(p))) {
    const chat =
      readLive().chats.find((c) => c.id === Number(m![1])) ??
      fail(404, "session_not_found", "Không tìm thấy cuộc trò chuyện.");
    return {
      items: chat.messages.map(
        ({ sent: _s, cited_chunks: _c, ...rest }: any) => rest,
      ),
      next_cursor: null,
    };
  }
  if ((m = /^\/messages\/(\d+)\/rating$/.exec(p)))
    return liveTransaction((s) => {
      for (const c of s.chats)
        for (const msg of c.messages)
          if (msg.id === Number(m![1])) msg.helpful = body.helpful;
      return { ok: true };
    });
  if ((m = /^\/chat\/suggestions\/(\d+)\/accept$/.exec(p))) {
    const found =
      readLive().suggestions[m[1]] ??
      fail(404, "suggestion_not_found", "Không tìm thấy gợi ý.");
    return {
      kind: "practise",
      practice_set_id: found.practice_set_id,
      for_date: null,
    };
  }
  if ((m = /^\/items\/([^/]+)\/hint$/.exec(p))) {
    // Written by code, not a model: the passage the question was written from, when it is known.
    const s = readLive();
    const q = s.questions[m[1]];
    const passage = q?.sources[0] ? s.passages[q.sources[0]] : undefined;
    return {
      text: passage
        ? `Đọc lại đoạn nguồn: ${passage.document}${passage.chapter ? ` › ${passage.chapter}` : ""}.`
        : "Tìm dữ kiện then chốt trong tình huống (đối tượng, thời điểm, dấu hiệu), rồi loại các phương án không khớp với hướng dẫn.",
      citations: [],
      generated: false,
    };
  }
  return undefined;
}

/** Reads NDJSON lines from a fetch body, handing each object over as it arrives. */
async function readLines(res: Response, onLine: (event: any) => Promise<void>) {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    let chunk: ReadableStreamReadResult<Uint8Array>;
    try {
      chunk = await reader.read();
    } catch {
      throw new LiveError(
        0,
        "network",
        "Mất kết nối với máy chủ giữa chừng. Vui lòng thử lại.",
      );
    }
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    let cut = buffer.indexOf("\n");
    while (cut !== -1) {
      const line = buffer.slice(0, cut).trim();
      buffer = buffer.slice(cut + 1);
      if (line) await onLine(JSON.parse(line));
      cut = buffer.indexOf("\n");
    }
  }
  if (buffer.trim()) await onLine(JSON.parse(buffer));
}

/** A topic quiz the model made: its items become a practice set, offered as a suggestion. */
async function offerSet(result: any): Promise<ChatSuggestion> {
  const set = await get(`/mcq/sets/${result.set_id}`);
  return liveTransaction((s) => {
    const id = nextId(s);
    s.practice[id] = {
      id,
      source: "chat_suggestion",
      competency_code: "",
      topic: result.title,
      card_id: null,
      scope: {
        de_muc: null,
        van_de: [...new Set(set.items.map((i: any) => i.van_de))],
      },
      completed: false,
      updated_at: new Date().toISOString(),
      items: set.items.map((item: any, n: number) => ({
        question_id: String(item.id),
        n: n + 1,
        stem: stemOf(item),
        options: Object.entries(item.options).map(([key, text]) => ({
          key,
          text,
        })),
        reason_vi: `Câu hỏi trong ngân hàng về “${result.title}”.`,
        van_de: item.van_de,
        bloom: item.bloom,
        chosen: null,
        feedback: null,
      })),
    };
    const suggestion = nextId(s);
    s.suggestions[suggestion] = { practice_set_id: id };
    return {
      id: suggestion,
      kind: "practise",
      label_vi: `Làm bài ${set.items.length} câu: ${result.title}`,
      reason_vi:
        set.notes.join(" ") || "Câu hỏi lấy từ ngân hàng của nền tảng.",
      n_items: set.items.length,
    } as ChatSuggestion;
  });
}

export async function liveStream(
  path: string,
  body: any,
  onEvent: (event: string, data: any) => void,
) {
  const explainOf = /^\/items\/([^/]+)\/explain$/.exec(path)?.[1];
  const chatId = Number(/^\/chat\/sessions\/(\d+)\/messages$/.exec(path)?.[1]);
  if (!explainOf && !chatId) fail(404, "not_found", "Không tìm thấy.");
  const s0 = readLive();
  const chat = chatId ? s0.chats.find((c) => c.id === chatId) : null;
  if (chatId && !chat)
    fail(404, "session_not_found", "Không tìm thấy cuộc trò chuyện.");
  const questionId = explainOf ?? chat?.question_id ?? null;
  const about = questionId ? aboutQuestion(s0, questionId) : null;
  if (questionId && !about)
    fail(409, "not_answered", "Hãy trả lời câu trước khi hỏi gia sư.");

  const asked = explainOf ? EXPLAIN : String(body.text ?? "").trim();
  if (asked.length > MAX_QUESTION)
    fail(
      422,
      "question_too_long",
      `Câu hỏi dài quá ${MAX_QUESTION} ký tự. Hãy rút gọn rồi gửi lại.`,
    );
  const earlier: any[] = chat?.messages ?? [];
  // The question block goes with the first turn, shortened if a long vignette would not fit;
  // later turns see it in the history.
  let question = asked;
  const room = MAX_QUESTION - asked.length - 2;
  if (about && !earlier.length && room > 1)
    question = `${about.text.length > room ? `${about.text.slice(0, room - 1)}…` : about.text}\n\n${asked}`;
  const lastAnswer = [...earlier].reverse().find((x) => x.role === "assistant");
  // The tutor move: the one asked for (a chip), the grading of a reply to a quiz question, or
  // (auto) read by the backend from the wording.
  const mode: string =
    body.mode ?? (lastAnswer?.mode === "kiem_tra" ? "cham" : "auto");
  // What was just discussed: the passages the last answer cited, or for a quiz question (which
  // cites nothing) the passages it was asked from. A broad answer can cite twenty; the backend
  // keeps the first few anyway.
  const discussed: string[] = lastAnswer?.cited_chunks?.length
    ? lastAnswer.cited_chunks
    : (lastAnswer?.source_chunks ?? []);
  const context: string[] = about?.context ?? discussed;
  const payload = {
    question,
    history: earlier
      .slice(-HISTORY)
      .map((x) => ({ role: x.role, content: x.sent ?? x.text })),
    context: context.slice(0, MAX_CONTEXT),
    mode,
  };

  const trace: StepEvent[] = [];
  const step = (id: string, label_vi: string, status: "running" | "done") => {
    const ev = { id, kind: id, label_vi, status };
    const at = trace.findIndex((t) => t.id === id);
    if (at === -1) trace.push(ev);
    else trace[at] = ev;
    onEvent("step", ev);
  };
  let citations: Citation[] = [];
  let text = "";
  const notices: string[] = [];
  const suggestions: ChatSuggestion[] = [];
  let toolUsed = false;
  let final: Record<string, any> | null = null;
  const answer = () =>
    onEvent("answer", {
      text: cites(text),
      citations,
      notice: notices.join(" ") || null,
    });

  // The answer is complete at "done": it is stored and shown then, without waiting for the
  // follow-up questions the backend may still be writing.
  const finish = (ev: { cited: number[]; mode?: string }) => {
    step("write", WRITE_STEP[ev.mode ?? ""] ?? WRITE_STEP.giai_thich, "done");
    const cited = new Set(ev.cited);
    const shown = citations.filter((c) => cited.has(c.n));
    if (!text.trim() && suggestions.length)
      text = "Mình đã tạo bài luyện từ ngân hàng câu hỏi.";
    // A quiz question cites nothing by design; any other answer without a citation found nothing.
    const state =
      shown.length || toolUsed || ev.mode === "kiem_tra"
        ? "answered"
        : "insufficient_evidence";
    final = {
      state,
      message_id: 0,
      trace_summary: null,
      clarify_options: [],
      searched:
        state === "insufficient_evidence"
          ? citations.map((c) => ({
              document: c.document,
              range: c.chapter ?? (c.page ? `trang ${c.page}` : ""),
            }))
          : [],
      nearest_chapter: null,
      suggestions,
      mode: ev.mode ?? null,
      follow_ups: [],
    };
    final.message_id = liveTransaction((s) => {
      const userId = nextId(s);
      const id = nextId(s);
      const c = chatId ? s.chats.find((x) => x.id === chatId) : null;
      if (c) {
        c.messages.push(
          message({ id: userId, role: "user", text: asked, sent: question }),
          message({
            id,
            role: "assistant",
            text: cites(text),
            sent: text,
            citations: shown,
            notice: notices.join(" ") || null,
            trace,
            cited_chunks: shown.map((x) => x.passage_id),
            source_chunks: citations.map((x) => x.passage_id),
            ...final,
          }),
        );
        if (c.title === NEW_TITLE) c.title = asked.slice(0, 70);
        c.updated_at = new Date().toISOString();
      }
      record(s, "chat", c?.title ?? "Giải thích câu hỏi", null);
      return id;
    });
    onEvent("answer", {
      text: cites(text),
      citations: shown,
      notice: notices.join(" ") || null,
    });
    onEvent("final", final);
  };

  onEvent("status", { status: "answering" });
  step("search", "Tìm trong tài liệu", "running");
  const res = await backendFetch("POST", "/chat", payload);
  await readLines(res, async (ev) => {
    if (ev.type === "plan") {
      step(
        "plan",
        ev.mode === "so_sanh"
          ? `So sánh ${ev.sections.join(", ")}${ev.aspect ? ` theo ${ev.aspect}` : ""}`
          : `Tổng hợp từ ${ev.sections.length} chương: ${ev.aspect}`,
        "done",
      );
    } else if (ev.type === "sources") {
      citations = liveTransaction((s) => rememberSources(s, ev.sources));
      step("search", `Tìm được ${ev.sources.length} đoạn nguồn`, "done");
      step("write", WRITE_STEP[mode] ?? WRITE_STEP.giai_thich, "running");
    } else if (ev.type === "delta") {
      text += ev.text;
      answer();
    } else if (ev.type === "tool") {
      toolUsed = true;
      const r = ev.result;
      if (!r.ok) notices.push(r.message);
      else if (ev.name === "tao_bai_trac_nghiem")
        suggestions.push(await offerSet(r));
      else if (ev.name === "them_the_on_tap")
        notices.push(`Đã tạo thẻ “${r.front}”. ${r.text}`);
      answer();
    } else if (ev.type === "done") {
      finish(ev);
    } else if (ev.type === "suggestions" && final) {
      const done = final;
      done.follow_ups = ev.items;
      liveTransaction((s) => {
        for (const c of s.chats)
          for (const msg of c.messages)
            if (msg.id === done.message_id) msg.follow_ups = ev.items;
      });
      onEvent("final", done);
    } else if (ev.type === "error") {
      throw new LiveError(502, "model_error", ev.message);
    }
  });
  if (!final)
    throw new LiveError(
      0,
      "network",
      "Câu trả lời bị ngắt giữa chừng. Vui lòng thử lại.",
    );
}
