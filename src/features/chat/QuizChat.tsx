import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Conversation } from "../../components/Conversation";
import { Icon } from "../../components/Icon";

// What the screen that opened the chat knows of the item. Kept in the router's state, so it survives
// a reload; a chat reached any other way has none and is an ordinary chat.
export type QuizChatContext = {
  label: string; // "Câu 3 · Luyện điểm yếu"
  stem: string;
  chosen: string | null; // the text of the option the learner chose
  correct: boolean;
  back: string; // where "Quay lại bài luyện" goes
  sessionId?: number; // the conversation, once started
};

// Hỏi gia sư · từ câu quiz (06-screens, mock ChatQuiz; FR-LRN-35): a chat about the item the
// learner just answered. The first answer explains the chosen option first (the server does that
// for a session opened with `question_id`); later questions are ordinary chat.
export function QuizChat() {
  const { questionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const context = location.state as QuizChatContext | null;

  const intro = context && (
    <section
      className="card row"
      aria-label="Đang hỏi về"
      style={{ alignItems: "flex-start" }}
    >
      <span
        style={{ color: "var(--primary-dark)", display: "flex", paddingTop: 2 }}
      >
        <Icon name="target" size={20} />
      </span>
      <span className="grow">
        <span className="h2" style={{ display: "block" }}>
          Đang hỏi về: {context.label}
        </span>
        <span className="muted">
          {context.stem}
          {context.chosen ? ` · bạn chọn ${context.chosen}` : ""}
        </span>
      </span>
    </section>
  );

  return (
    <div className="screen tutor tutor-quiz">
      <header className="topbar">
        <button
          className="icon-btn"
          aria-label="Quay lại"
          onClick={() => navigate(context?.back ?? "/hoi-dap")}
        >
          <Icon name="left" />
        </button>
        <h1>Hỏi gia sư</h1>
      </header>
      <section className="conversation-panel" aria-label="Nội dung hội thoại">
        <Conversation
          sessionId={context?.sessionId ?? null}
          onSession={(id) =>
            context &&
            navigate(location.pathname, {
              replace: true,
              state: { ...context, sessionId: id },
            })
          }
          questionId={context ? questionId : undefined}
          starters={
            context
              ? [
                  context.correct
                    ? "Giải thích thêm về câu này"
                    : "Sao mình sai câu này?",
                ]
              : []
          }
          intro={intro}
          quiz={context ? { back: context.back } : undefined}
        />
      </section>
    </div>
  );
}
