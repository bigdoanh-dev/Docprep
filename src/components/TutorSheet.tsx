import { useEffect, useState } from "react";
import { ApiError, api, type Citation, type Hint } from "../lib/api";
import { postSSE } from "../lib/sse";
import { AiStar } from "./AiStar";
import {
  AnswerText,
  CitationChip,
  StatusLine,
  type AnswerResult,
  type StreamStatus,
} from "./Answer";
import { Sheet } from "./Sheet";

// Tutor sheet on a quiz item (R1.0), with no free-text input. Two actions, each its own mode:
//   hint     "Gợi ý", before the answer: one hint, fetched once for as long as the item is shown.
//   explain  "Giải thích thêm", after the answer, grounded in the item's source and the expert explanation.
export function TutorSheet({
  open,
  onClose,
  questionId,
  topic,
  onCite,
  mode = "explain",
}: {
  open: boolean;
  onClose: () => void;
  questionId: string;
  topic: string;
  onCite: (c: Citation) => void;
  mode?: "explain" | "hint";
}) {
  const [status, setStatus] = useState<StreamStatus>();
  const [result, setResult] = useState<AnswerResult>();
  const [hint, setHint] = useState<Hint>();
  const [refused, setRefused] = useState<string>(); // the server will not give a hint here: asking again changes nothing
  const [error, setError] = useState<string>();

  const explain = async () => {
    setStatus("answering");
    setResult(undefined);
    setError(undefined);
    try {
      let answer: AnswerResult | undefined;
      await postSSE(`/items/${questionId}/explain`, {}, (event, data) => {
        if (event === "status") setStatus(data.status);
        else if (event === "answer")
          answer = {
            state: "answered",
            text: data.text,
            citations: data.citations,
            notice: data.notice,
          };
        else if (event === "final" && answer)
          setResult({ ...answer, state: data.state });
      });
      if (!answer)
        throw new Error("Không nhận được giải thích. Vui lòng thử lại.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStatus(undefined);
    }
  };

  const askHint = async () => {
    setStatus("answering");
    setError(undefined);
    try {
      setHint(await api.post<Hint>(`/items/${questionId}/hint`));
    } catch (e) {
      if (e instanceof ApiError && e.code === "hint_unavailable")
        setRefused(e.message);
      else setError((e as Error).message);
    } finally {
      setStatus(undefined);
    }
  };

  const ask = mode === "hint" ? askHint : explain;
  const settled =
    mode === "hint"
      ? hint !== undefined || refused !== undefined
      : result !== undefined;

  // Start as soon as the sheet opens for a question that has nothing to show yet.
  useEffect(() => {
    if (open && !settled && !status && !error) ask();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, questionId]);

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={mode === "hint" ? "Gợi ý" : "Phần hỏi đáp"}
    >
      <div className="stack" aria-live="polite">
        <p className="muted small">Đang hỏi về: {topic}</p>
        {status && <StatusLine status={status} />}
        {hint && (
          <>
            {hint.generated && (
              <p
                className="row small"
                style={{ gap: 6, color: "var(--text-2)", fontWeight: 600 }}
              >
                <AiStar size={16} />
                Gợi ý do AI viết
              </p>
            )}
            <p style={{ fontSize: 16, lineHeight: 1.7 }}>{hint.text}</p>
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {hint.citations.map((c) => (
                <CitationChip
                  key={c.passage_id}
                  citation={c}
                  onOpen={onCite}
                  label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
                />
              ))}
            </div>
            <p className="muted small">
              Gợi ý chỉ đường tới chỗ cần xem lại, không cho biết đáp án.
            </p>
          </>
        )}
        {refused && <p className="note">{refused}</p>}
        {result?.state === "answered" && (
          <AnswerText result={result} onCite={onCite} />
        )}
        {result && result.state !== "answered" && (
          <>
            <p>{result.text}</p>
            {result.notice && <p className="note">{result.notice}</p>}
          </>
        )}
        {error && <p role="alert">{error}</p>}
        {!status && (error || (result && result.state !== "answered")) && (
          <div>
            <button className="btn" onClick={ask}>
              Thử lại
            </button>
          </div>
        )}
        {result?.state === "answered" && (
          <p className="muted small">
            Giải thích dựa trên tài liệu nguồn và lời giải kèm theo câu hỏi.
          </p>
        )}
      </div>
    </Sheet>
  );
}
