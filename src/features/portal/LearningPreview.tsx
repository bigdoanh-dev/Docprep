import { useEffect, useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  BookOpen,
  ClipboardCheck,
  ChartNoAxesColumnIncreasing,
  MessagesSquare,
  Pause,
  Play,
  ArrowRight,
  Check,
  RotateCcw,
  Sparkles,
  ShieldCheck,
  Clock,
  User,
  GraduationCap,
  BookmarkCheck,
} from "lucide-react";

interface MethodItem {
  id: string;
  label: string;
  icon: typeof MessagesSquare;
  tag: string;
  title: string;
  description: string;
  detail: string;
  badgeText: string;
}

const methods: MethodItem[] = [
  {
    id: "source",
    label: "Hỏi đáp có nguồn",
    icon: MessagesSquare,
    tag: "Trích dẫn giáo trình",
    badgeText: "Có tài liệu để đối chiếu",
    title: "Hiểu sâu bản chất, đối chiếu tận gốc y văn.",
    description:
      "Đặt câu hỏi theo từng học phần, đọc lời giải thích mở rộng và tra cứu trực tiếp đoạn tài liệu tham khảo chính thống từ Bộ Y tế và Đại học Y Hà Nội.",
    detail:
      "Đọc đoạn tài liệu liên quan để hiểu vì sao chọn đáp án, thay vì chỉ ghi nhớ đáp án đúng.",
  },
  {
    id: "practice",
    label: "Luyện tập câu hỏi",
    icon: BookOpen,
    tag: "Khung năng lực BYT",
    badgeText: "Phân tích vì sao đúng – sai",
    title: "Làm một câu. Hiểu thêm một cơ chế sinh bệnh.",
    description:
      "Luyện tập theo 8 nhóm chuẩn năng lực cốt lõi. Mỗi câu hỏi đi kèm phản hồi phân tích chi tiết vì sao một phương án đúng và vì sao các phương án khác chưa phù hợp.",
    detail:
      "Những điểm còn phân vân sẽ được hệ thống tự động lưu vào sổ tay và đưa vào chu kỳ nhắc ôn chống quên.",
  },
  {
    id: "exam",
    label: "Thi thử trên máy tính",
    icon: ClipboardCheck,
    tag: "Ôn tập theo phạm vi đề tài",
    badgeText: "Đếm ngược & Tự lưu bài",
    title: "Mô phỏng áp lực phòng thi máy tính thực tế.",
    description:
      "Rèn luyện kỹ năng phân bổ thời gian, đánh dấu câu phân vân để rà soát và trải nghiệm giao diện thi trắc nghiệm trên máy tính để luyện cách làm bài và quản lý thời gian.",
    detail:
      "Khóa hoàn toàn trợ lý giải đáp trong giờ thi nhằm bảo đảm tính trung thực và phản ánh đúng năng lực hiện tại.",
  },
  {
    id: "progress",
    label: "Phân tích năng lực",
    icon: ChartNoAxesColumnIncreasing,
    tag: "Đánh giá đa cấp độ",
    badgeText: "Từ lý thuyết đến ca bệnh",
    title: "Nhận diện điểm mạnh, khắc phục lỗ hổng kiến thức.",
    description:
      "Theo dõi phổ điểm và tỷ lệ hoàn thành theo từng nhóm năng lực. Hệ thống tự động phân loại mức độ nhận thức từ câu hỏi nhớ kiến thức đến xử lý tình huống thực địa.",
    detail:
      "Biểu đồ phân tích liên tục cập nhật theo từng phiên học giúp bạn biết chính xác mình đang sẵn sàng ở mức nào.",
  },
];

const options = [
  "Chỉ các ca bệnh mới phát hiện trong tuần",
  "Tất cả các ca bệnh hiện có tại thời điểm khảo sát (gồm cả ca cũ và mới)",
  "Chỉ những người bệnh có biểu hiện triệu chứng lâm sàng nặng",
  "Tổng số lượt khám bệnh tích lũy tại trạm y tế trong năm",
];

export function LearningPreview() {
  const instance = useId();
  const reduced = useReducedMotion();
  const [active, setActive] = useState(0);
  const [autoplay, setAutoplay] = useState(false);
  const [held, setHeld] = useState(false);
  const [visible, setVisible] = useState(true);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [answer, setAnswer] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [seconds, setSeconds] = useState(180);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  useEffect(() => {
    if (!autoplay || held || reduced || !visible) return;
    const timer = window.setInterval(
      () => setActive((previous) => (previous + 1) % methods.length),
      7000,
    );
    return () => window.clearInterval(timer);
  }, [autoplay, held, reduced, visible]);

  useEffect(() => {
    if (!running || active !== 2 || submitted) return;
    const timer = window.setInterval(
      () => setSeconds((value) => Math.max(0, value - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [running, active, submitted]);

  const method = methods[active];

  return (
    <div className="learning-preview modern-preview-card">
      {/* Modern Toolbar */}
      <div className="preview-toolbar modern-preview-toolbar">
        <div
          className="preview-tabs modern-preview-tabs"
          role="tablist"
          aria-label="Khám phá cách học"
        >
          {methods.map((item, index) => {
            const Icon = item.icon;
            const isSelected = active === index;
            return (
              <button
                type="button"
                key={item.id}
                role="tab"
                id={`${instance}-tab-${index}`}
                aria-controls={`${instance}-panel-${index}`}
                aria-selected={isSelected}
                tabIndex={isSelected ? 0 : -1}
                className={`modern-preview-tab-btn ${isSelected ? "active" : ""}`}
                onClick={() => setActive(index)}
                onKeyDown={(event) => {
                  let next = index;
                  if (event.key === "ArrowRight")
                    next = (index + 1) % methods.length;
                  else if (event.key === "ArrowLeft")
                    next = (index - 1 + methods.length) % methods.length;
                  else if (event.key === "Home") next = 0;
                  else if (event.key === "End") next = methods.length - 1;
                  else return;
                  event.preventDefault();
                  setActive(next);
                  document.getElementById(`${instance}-tab-${next}`)?.focus();
                }}
              >
                <Icon size={16} />
                <span>{item.label}</span>
                {isSelected && (
                  <motion.span
                    className="preview-tab-line modern-tab-pill"
                    layoutId={`${instance}-indicator`}
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          className="preview-play modern-preview-play"
          aria-pressed={autoplay}
          disabled={Boolean(reduced)}
          onClick={() => setAutoplay((value) => !value)}
          aria-label={
            autoplay ? "Dừng tự chuyển nội dung" : "Tự chuyển nội dung"
          }
        >
          {autoplay ? <Pause size={14} /> : <Play size={14} />}
          <span>{autoplay ? "Tạm dừng" : "Tự chuyển"}</span>
        </button>
      </div>

      {/* Main Panel: Left Description, Right Simulated App */}
      <div
        className="preview-panel modern-preview-panel"
        role="tabpanel"
        id={`${instance}-panel-${active}`}
        aria-labelledby={`${instance}-tab-${active}`}
        tabIndex={0}
      >
        {/* Left Column: Context & Pedagogical Value */}
        <div className="preview-copy modern-preview-copy">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={method.id}
              initial={{ opacity: 0, y: reduced ? 0 : 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduced ? 0 : -8 }}
              transition={{ duration: 0.22 }}
            >
              <div className="preview-tag-strip">
                <span className="modern-feature-pill">{method.tag}</span>
                <span className="modern-feature-badge">
                  <Sparkles size={13} /> {method.badgeText}
                </span>
              </div>

              <h3>{method.title}</h3>
              <p className="preview-lead-desc">{method.description}</p>

              <div className="modern-callout-box">
                <ShieldCheck size={18} className="callout-icon" />
                <p className="preview-detail">{method.detail}</p>
              </div>

              <div className="preview-action-row">
                <a href="#lo-trinh-tinh-nang" className="preview-action-link">
                  <span>Xem chi tiết nghiệp vụ</span>
                  <ArrowRight size={15} />
                </a>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Right Column: Simulated App UI Window */}
        <div
          className="preview-workspace modern-preview-workspace"
          onMouseEnter={() => setHeld(true)}
          onMouseLeave={() => setHeld(false)}
          onFocusCapture={() => setHeld(true)}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget))
              setHeld(false);
          }}
        >
          {/* Clinical Application Header Bar */}
          <div className="preview-window-bar modern-window-bar">
            <div className="clinical-header-identity">
              <span className="clinical-app-icon">
                <method.icon size={15} />
              </span>
              <span className="preview-window-title">
                DocPrep YHDP · Không gian Khảo thí & Luyện tập Y học dự phòng
              </span>
            </div>
            <span className="window-status-chip">
              <span className="status-live-dot" />
              Chế độ mô phỏng
            </span>
          </div>

          {/* Interactive Screen Contents */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={method.id}
              className={`preview-screen modern-screen screen-${method.id}`}
              initial={{ opacity: 0, x: reduced ? 0 : 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: reduced ? 0 : -10 }}
              transition={{ duration: 0.24 }}
            >
              {/* Tab 1: AI Tutor gợi mở từng bước Chat */}
              {active === 0 && (
                <div className="interactive-chat-view">
                  <div className="chat-bubble-user">
                    <div className="chat-bubble-header">
                      <User size={13} />
                      <span>Học viên YHDP</span>
                    </div>
                    <p>Hiện mắc (Prevalence) và mới mắc (Incidence) khác nhau ở điểm nào trong dịch tễ học thực địa?</p>
                  </div>

                  <div className="chat-bubble-tutor">
                    <div className="chat-tutor-meta">
                      <GraduationCap size={15} className="tutor-icon-accent" />
                      <strong>Trợ lý giải đáp y khoa (Đối chiếu giáo trình)</strong>
                      <span className="tutor-verified-tag">Tài liệu tham khảo</span>
                    </div>
                    <div className="chat-tutor-body">
                      <p>
                        Chào bạn! Điểm khác biệt mấu chốt trong giám sát dịch tễ học:
                      </p>
                      <ul className="tutor-bullet-list">
                        <li>
                          <strong>Hiện mắc (Prevalence - P):</strong> Đo lường <em>tất cả các ca bệnh đang có</em> tại một thời điểm hoặc khoảng thời gian xác định (bao gồm cả ca cũ và ca mới).
                        </li>
                        <li>
                          <strong>Mới mắc (Incidence - I):</strong> Chỉ đếm các ca bệnh <em>mới xuất hiện</em> trong một khoảng thời gian theo dõi trên quần thể có nguy cơ.
                        </li>
                      </ul>
                    </div>

                    <button
                      type="button"
                      className={`preview-source modern-source-btn ${sourceOpen ? "expanded" : ""}`}
                      aria-expanded={sourceOpen}
                      onClick={() => setSourceOpen((value) => !value)}
                    >
                      <BookOpen size={14} />
                      <span>Giáo trình Dịch tễ học cơ bản · Tr. 58–59 (ĐHYHN)</span>
                      <ArrowRight size={14} className={`source-arrow ${sourceOpen ? "rotated" : ""}`} />
                    </button>

                    <AnimatePresence initial={false}>
                      {sourceOpen && (
                        <motion.div
                          className="preview-excerpt modern-excerpt-card"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <div className="excerpt-header">
                            <BookmarkCheck size={14} />
                            <span>Trích dẫn nguyên văn giáo trình Bộ Y tế:</span>
                          </div>
                          <p>&ldquo;Tỷ lệ hiện mắc phản ánh gánh nặng bệnh tật trong quần thể tại thời điểm nghiên cứu, là cơ sở để hoạch định nhu cầu dịch vụ y tế và thuốc men tại trạm y tế.&rdquo;</p>
                          <small>Bộ Y tế · Quyết định số 2760/QĐ-BYT về Giám sát dịch tễ học</small>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              )}

              {/* Tab 2: Question Practice Runner */}
              {active === 1 && (
                <div className="interactive-practice-view">
                  <div className="practice-meta-strip">
                    <span className="practice-group-tag">Nhóm 1 · Sức khỏe quần thể & Dịch tễ</span>
                    <span className="practice-level-tag">Mức 2 · Hiểu kiến thức</span>
                  </div>

                  <h4 className="practice-question-text">
                    Tử số của tỷ lệ hiện mắc (Prevalence) bao gồm những trường hợp nào?
                  </h4>

                  <div className="preview-options modern-practice-options">
                    {options.map((option, index) => {
                      const isChosen = answer === index;
                      const isCorrect = index === 1;
                      return (
                        <button
                          type="button"
                          key={option}
                          aria-pressed={isChosen}
                          className={`practice-opt-btn ${isChosen ? (isCorrect ? "opt-correct" : "opt-wrong") : ""}`}
                          onClick={() => setAnswer(index)}
                        >
                          <span className="opt-letter-circle">
                            {String.fromCharCode(65 + index)}
                          </span>
                          <span className="opt-text-label">{option}</span>
                          {isChosen && (
                            <span className="opt-status-icon">
                              <Check size={15} />
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  <AnimatePresence initial={false}>
                    {answer !== null && (
                      <motion.div
                        className={`practice-feedback-card ${answer === 1 ? "correct" : "warning"}`}
                        role="status"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <strong>
                          {answer === 1 ? "✓ Đáp án chính xác!" : "⚠ Cần lưu ý đối chiếu:"}
                        </strong>
                        <p>
                          {answer === 1
                            ? "Tử số của tỷ lệ hiện mắc (P) phải bao gồm toàn bộ ca bệnh đang tồn tại (cả ca mắc từ trước lẫn ca mới phát sinh) tại thời điểm khảo sát."
                            : "Tỷ lệ hiện mắc phản ánh toàn bộ gánh nặng bệnh tật hiện có, nên phải tính cả ca cũ và ca mới. Chỉ đếm ca mới là đặc trưng của tỷ lệ mới mắc (Incidence)."}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* Tab 3: CBT Exam Simulation */}
              {active === 2 && (
                <div className="interactive-exam-view">
                  <div className="preview-exam-top modern-exam-bar">
                    <div className="exam-mode-badge">
                      <span className="exam-live-dot" />
                      <span>Bài thi thử theo phạm vi đề tài</span>
                    </div>

                    <div className="exam-countdown-box">
                      <Clock size={15} />
                      <strong>
                        {Math.floor(seconds / 60)
                          .toString()
                          .padStart(2, "0")}
                        :{(seconds % 60).toString().padStart(2, "0")}
                      </strong>
                    </div>
                  </div>

                  <div className="preview-question-map modern-stepper-grid">
                    {Array.from({ length: 16 }, (_, index) => {
                      const isDone = index < 6;
                      const isCurrent = index === 6;
                      const isFlagged = index === 2 || index === 9;
                      return (
                        <span
                          key={index}
                          className={`stepper-pill ${isDone ? "done" : ""} ${isCurrent ? "current" : ""} ${isFlagged ? "flagged" : ""}`}
                        >
                          {index + 1}
                        </span>
                      );
                    })}
                  </div>

                  <div className="exam-status-meta">
                    <span className="meta-item"><span className="legend-dot done" /> Đã trả lời: 6</span>
                    <span className="meta-item"><span className="legend-dot flagged" /> Đánh dấu xem lại: 2</span>
                    <span className="meta-item"><span className="legend-dot current" /> Câu hiện tại: 7</span>
                  </div>

                  <div className="exam-preview-content">
                    <p className="exam-prompt-headline">
                      {submitted || seconds === 0
                        ? "Phiên làm bài minh họa đã hoàn tất."
                        : "Câu 7: Một ổ dịch Sốt xuất huyết được coi là chấm dứt khi thỏa mãn tiêu chí nào?"}
                    </p>
                    <p className="exam-subtext">
                      {submitted
                        ? "Hệ thống đã tự động thu bài và khóa trợ lý giải đáp. Báo cáo phân tích phổ điểm chi tiết theo từng nhóm năng lực đang sẵn sàng."
                        : "Thời gian làm bài tiếp tục trôi khi chuyển câu. Mọi câu trả lời được hệ thống tự động lưu tức thời, không lo mất bài."}
                    </p>
                  </div>

                  <div className="preview-exam-actions modern-exam-actions">
                    <button
                      type="button"
                      onClick={() => {
                        if (submitted || seconds === 0) {
                          setSubmitted(false);
                          setSeconds(180);
                          setRunning(false);
                        } else setRunning((value) => !value);
                      }}
                      className="preview-action modern-btn-outline"
                    >
                      {submitted || seconds === 0 ? (
                        <RotateCcw size={15} />
                      ) : running ? (
                        <Pause size={15} />
                      ) : (
                        <Play size={15} />
                      )}
                      <span>
                        {submitted || seconds === 0
                          ? "Làm lại bài thi"
                          : running
                            ? "Tạm dừng đồng hồ"
                            : "Bật đồng hồ đếm ngược"}
                      </span>
                    </button>

                    {!submitted && seconds > 0 && (
                      <button
                        type="button"
                        className="preview-submit modern-btn-submit"
                        onClick={() => {
                          setSubmitted(true);
                          setRunning(false);
                        }}
                      >
                        <ClipboardCheck size={15} />
                        <span>Nộp bài và xem kết quả</span>
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 4: Progress & Bloom Matrix Analytics */}
              {active === 3 && (
                <div className="interactive-progress-view">
                  <div className="progress-meta-strip">
                    <span className="progress-title-tag">Báo cáo năng lực cá nhân</span>
                    <span className="progress-date-tag">Cập nhật theo thời gian thực</span>
                  </div>

                  <div className="preview-bars modern-bars-container">
                    {[
                      { name: "Sức khỏe quần thể & Dịch tễ học", pct: 84, color: "#0284c7" },
                      { name: "Cấp cứu ban đầu & Xử trí khẩn cấp", pct: 72, color: "#10b981" },
                      { name: "Dinh dưỡng & An toàn thực phẩm", pct: 90, color: "#f59e0b" },
                      { name: "Bệnh truyền nhiễm & Bệnh nghề nghiệp", pct: 64, color: "#6366f1" },
                    ].map((item) => (
                      <div key={item.name} className="modern-bar-row">
                        <div className="bar-labels">
                          <span className="bar-title">{item.name}</span>
                          <strong className="bar-pct">{item.pct}%</strong>
                        </div>
                        <div className="preview-track modern-track">
                          <motion.span
                            style={{ background: item.color }}
                            initial={{ width: 0 }}
                            animate={{ width: `${item.pct}%` }}
                            transition={{ duration: reduced ? 0 : 0.8 }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bloom-mini-matrix">
                    <div className="bloom-chip">
                      <strong>92%</strong>
                      <span>Mức 1–2: Nhớ & Hiểu</span>
                    </div>
                    <div className="bloom-chip">
                      <strong>78%</strong>
                      <span>Mức 3–4: Vận dụng & Phân tích</span>
                    </div>
                    <div className="bloom-chip">
                      <strong>Sẵn sàng</strong>
                      <span>Đánh giá & Xử trí</span>
                    </div>
                  </div>

                  <div className="preview-next modern-next-step-box">
                    <BookOpen size={18} className="next-step-icon" />
                    <div>
                      <span className="next-step-sub">Khuyến nghị lộ trình tiếp theo</span>
                      <strong>Tăng cường 4 vấn đề Bệnh truyền nhiễm & Bệnh nghề nghiệp</strong>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
