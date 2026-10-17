import {
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  Stethoscope,
  HeartPulse,
  HeartHandshake,
  ShieldAlert,
  ListChecks,
  Sparkles,
  Info,
} from "lucide-react";
import { useState } from "react";
import { useActor } from "../../app/identity";
import { recordActivity } from "../../lib/learnerWorkspace";
import { SaveQuestion } from "../../components/SaveQuestion";

const caseVisuals: Record<
  string,
  {
    Icon: React.ElementType;
    tag: string;
    badgeBg: string;
    badgeColor: string;
    headerGrad: string;
    iconBg: string;
    iconColor: string;
    highlightTag: string;
  }
> = {
  breathing: {
    Icon: HeartPulse,
    tag: "Cấp cứu ban đầu",
    badgeBg: "#ffe4e6",
    badgeColor: "#be123c",
    headerGrad: "linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%)",
    iconBg: "#ffffff",
    iconColor: "#e11d48",
    highlightTag: "Quy trình ABCDE",
  },
  handover: {
    Icon: HeartHandshake,
    tag: "Giao tiếp & An toàn",
    badgeBg: "#ede9fe",
    badgeColor: "#6d28d9",
    headerGrad: "linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)",
    iconBg: "#ffffff",
    iconColor: "#7c3aed",
    highlightTag: "Cấu trúc SBAR",
  },
  surveillance: {
    Icon: ShieldAlert,
    tag: "Y học dự phòng",
    badgeBg: "#ccfbf1",
    badgeColor: "#0f766e",
    headerGrad: "linear-gradient(135deg, #f0fdfa 0%, #e6fffa 100%)",
    iconBg: "#ffffff",
    iconColor: "#0d9488",
    highlightTag: "Giám sát dịch tễ",
  },
};
const cases = [
  {
    id: "breathing",
    title: "Tiếp nhận người bệnh khó thở",
    specialty: "Cấp cứu",
    description:
      "Trong ca trực, một người bệnh đến vì khó thở tăng dần. Rèn cách nhận diện ưu tiên và tiếp cận ban đầu có hệ thống.",
    source: "WHO–ICRC Basic Emergency Care",
    url: "https://www.who.int/publications/i/item/basic-emergency-care-approach-to-the-acutely-ill-and-injured",
    steps: [
      {
        title: "Nhận định ưu tiên",
        question: "Ở tình huống mô phỏng này, cách tiếp cận nào phù hợp?",
        options: [
          "Đánh giá ban đầu theo ABCDE và huy động hỗ trợ khi có dấu hiệu đe dọa tính mạng",
          "Chờ khai thác toàn bộ bệnh sử trước khi đánh giá ban đầu",
          "Kết luận nguyên nhân ngay từ triệu chứng khó thở",
        ],
        correct: 0,
        feedback:
          "ABCDE giúp tổ chức đánh giá ban đầu, nhận diện và ưu tiên các đe dọa tính mạng.",
      },
      {
        title: "Tiếp tục đánh giá",
        question:
          "Sau khi xử lý ưu tiên ban đầu trong mô phỏng, bước học tập tiếp theo là gì?",
        options: [
          "Chỉ ghi lại chẩn đoán ban đầu",
          "Đánh giá lại có hệ thống và thu thập bệnh sử theo SAMPLE",
          "Ngừng theo dõi vì đã đánh giá lần đầu",
        ],
        correct: 1,
        feedback:
          "Đánh giá lại và thu thập bệnh sử có cấu trúc giúp phát hiện thay đổi và hoàn thiện thông tin.",
      },
    ],
  },
  {
    id: "handover",
    title: "Bàn giao một ca có diễn biến mới",
    specialty: "Giao tiếp và an toàn người bệnh",
    description:
      "Cuối ca trực, bạn bàn giao người bệnh có diễn biến mới cho đồng nghiệp. Luyện giao tiếp đủ thông tin và kiểm tra sự tiếp nhận.",
    source:
      "WHO Patient Safety Solutions: Communication during patient handovers",
    url: "https://www.who.int/teams/integrated-health-services/patient-safety/research/patient-safety-solutions",
    steps: [
      {
        title: "Tổ chức thông tin",
        question: "Cấu trúc nào giúp bàn giao rõ ràng hơn trong ca mô phỏng?",
        options: [
          "Chỉ đọc tên và số giường",
          "Thông báo “cần theo dõi thêm” rồi kết thúc",
          "SBAR: tình huống, bối cảnh, nhận định và đề xuất",
        ],
        correct: 2,
        feedback:
          "Cấu trúc SBAR giúp truyền đạt có thứ tự các thông tin cần thiết khi bàn giao.",
      },
      {
        title: "Kiểm tra tiếp nhận",
        question: "Bạn nên kết thúc buổi bàn giao như thế nào?",
        options: [
          "Dành thời gian hỏi lại, làm rõ thông tin và xác nhận việc tiếp nhận",
          "Chỉ gửi tin nhắn vào nhóm rồi rời đi",
          "Cho rằng đồng nghiệp đã hiểu vì không đặt câu hỏi",
        ],
        correct: 0,
        feedback:
          "Trao đổi hai chiều và cơ hội làm rõ thông tin giúp hạn chế thiếu sót khi chuyển giao chăm sóc.",
      },
    ],
  },
  {
    id: "surveillance",
    title: "Phát hiện cụm ca bệnh tại địa bàn",
    specialty: "Y học dự phòng",
    description:
      "Báo cáo địa bàn ghi nhận số ca tăng. Rèn tư duy kiểm tra dữ liệu trước khi nhận định.",
    source: "Học liệu dịch tễ minh họa của nền tảng",
    url: "",
    steps: [
      {
        title: "Kiểm tra tín hiệu",
        question: "Điều gì cần kiểm tra trước khi so sánh số ca báo cáo?",
        options: [
          "Tính nhất quán của định nghĩa ca và chất lượng báo cáo",
          "Kết luận ngay nguyên nhân từ tổng số ca",
        ],
        correct: 0,
        feedback:
          "Kiểm tra khả năng so sánh của dữ liệu trước khi đưa ra nhận định.",
      },
      {
        title: "Mô tả dữ liệu",
        question: "Nên tổ chức dữ liệu theo các chiều nào?",
        options: ["Chỉ giữ tổng số ca", "Người, nơi và thời gian"],
        correct: 1,
        feedback:
          "Mô tả theo người, nơi và thời gian giúp tổ chức thông tin dịch tễ.",
      },
    ],
  },
];
export function CasePractice() {
  const actor = useActor()!,
    [selected, setSelected] = useState<string | null>(null),
    [step, setStep] = useState(0),
    [picked, setPicked] = useState<number | null>(null),
    [checked, setChecked] = useState(false),
    [answers, setAnswers] = useState<boolean[]>([]);
  const c = cases.find((c) => c.id === selected),
    current = c?.steps[step];
  const reset = () => {
    setSelected(null);
    setStep(0);
    setPicked(null);
    setChecked(false);
    setAnswers([]);
  };
  return (
    <div className="screen stack">
      <header className="page-heading">
        <h1>Rèn luyện ca lâm sàng</h1>
        <p>
          Luyện suy luận và giao tiếp qua những tình huống thường gặp khi hành
          nghề.
        </p>
      </header>
      <div className="case-notice-card">
        <Info size={18} className="case-notice-icon" />
        <p>
          Ca học tập mô phỏng, chưa được chuyên gia thẩm định. Không dùng để quyết
          định xử trí người bệnh; không cộng vào điểm năng lực.
        </p>
      </div>
      {actor.mode !== "demo" && (
        <p className="notice">
          Kho ca được duyệt và lưu kết quả trên máy chủ đang xây dựng.
        </p>
      )}
      {!c ? (
        <div className="case-grid">
          {cases.map((c) => {
            const visual = caseVisuals[c.id] || {
              Icon: Stethoscope,
              tag: c.specialty,
              badgeBg: "#e0f2fe",
              badgeColor: "#0369a1",
              headerGrad: "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)",
              iconBg: "#ffffff",
              iconColor: "#0284c7",
              highlightTag: "Tình huống lâm sàng",
            };
            const CaseIcon = visual.Icon;
            return (
              <article
                className="case-card"
                key={c.id}
                style={{ borderTop: `3px solid ${visual.iconColor}` }}
              >
                <div className="case-card-top">
                  <div className="case-card-specialty-group">
                    <span
                      className="case-card-icon"
                      style={{
                        background: visual.badgeBg,
                        color: visual.iconColor,
                      }}
                    >
                      <CaseIcon size={17} />
                    </span>
                    <span
                      className="case-specialty-tag"
                      style={{ color: visual.iconColor }}
                    >
                      {c.specialty}
                    </span>
                  </div>
                  <span className="case-framework-tag">
                    {visual.highlightTag}
                  </span>
                </div>
                <div className="case-card-content">
                  <h2>{c.title}</h2>
                  <p>{c.description}</p>
                </div>
                <div className="case-card-footer">
                  <div className="case-meta-row">
                    <span className="case-meta-item">
                      <ListChecks size={13} />
                      {c.steps.length} bước tình huống
                    </span>
                    <span className="case-meta-divider">·</span>
                    <span className="case-meta-item">
                      <Sparkles size={13} />
                      Phản hồi tức thì
                    </span>
                  </div>
                  <button
                    className="btn primary compact-btn case-btn"
                    disabled={actor.mode !== "demo"}
                    onClick={() => setSelected(c.id)}
                  >
                    <span>Bắt đầu ca</span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <>
          <button className="textlink row" onClick={reset}>
            <ArrowLeft size={17} /> Danh sách ca
          </button>
          <section className="panel stack">
            <span className="muted">{c.specialty}</span>
            <h2>{c.title}</h2>
            {current ? (
              <>
                <div className="progress">
                  <span
                    style={{ width: `${(step / c.steps.length) * 100}%` }}
                  />
                </div>
                <p className="muted">
                  Bước {step + 1}/{c.steps.length}: {current.title}
                </p>
                <h3>{current.question}</h3>
                {current.options.map((o, i) => (
                  <button
                    key={o}
                    className={`case-option ${picked === i ? "selected" : ""}`}
                    aria-pressed={picked === i}
                    disabled={checked}
                    onClick={() => setPicked(i)}
                  >
                    <span>{String.fromCharCode(65 + i)}</span>
                    {o}
                  </button>
                ))}
                {!checked ? (
                  <button
                    className="btn primary"
                    disabled={picked === null}
                    onClick={() => {
                      setChecked(true);
                      setAnswers((a) => [...a, picked === current.correct]);
                    }}
                  >
                    Xem phản hồi
                  </button>
                ) : (
                  <div className="notice stack" aria-live="polite">
                    <strong>
                      {picked === current.correct
                        ? "Lựa chọn phù hợp"
                        : "Cần xem lại cách tiếp cận"}
                    </strong>
                    <p>{current.feedback}</p>
                    <button
                      className="btn primary"
                      onClick={() => {
                        if (step + 1 === c.steps.length)
                          recordActivity(`case:${c.id}:${Date.now()}`, "case");
                        setStep(step + 1);
                        setPicked(null);
                        setChecked(false);
                      }}
                    >
                      {step + 1 === c.steps.length
                        ? "Hoàn thành ca"
                        : "Sang bước tiếp theo"}
                    </button>
                  </div>
                )}
                <SaveQuestion
                  id={`case:${c.id}:${step}`}
                  title={current.question}
                  detail={checked ? current.feedback : undefined}
                  source={c.source}
                />
              </>
            ) : (
              <div className="empty">
                <CheckCircle2 size={38} />
                <h2>Đã hoàn thành ca học tập</h2>
                <p>
                  {answers.filter(Boolean).length}/{answers.length} lựa chọn phù
                  hợp trong mô phỏng. Đây không phải điểm đánh giá năng lực.
                </p>
                <button className="btn primary" onClick={reset}>
                  Luyện một ca khác
                </button>
              </div>
            )}
            <p className="muted small">
              Nguồn tham khảo:{" "}
              {c.url ? (
                <a
                  className="textlink"
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {c.source}
                </a>
              ) : (
                c.source
              )}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
