import { useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  FileCheck2,
  GraduationCap,
  HeartHandshake,
  HeartPulse,
  HardHat,
  HousePlus,
  Layers,
  LineChart,
  MessagesSquare,
  Microscope,
  Salad,
  Stethoscope,
} from "lucide-react";
import { ScrollReveal } from "../../components/ScrollReveal";
import { useActor, roleHome } from "../../app/identity";
import { PortalHeader } from "../portal/PortalHeader";
import { PortalFooter } from "../portal/PortalFooter";
import { AntigravityHero } from "./AntigravityHero";

interface SimulatedTab {
  id: string;
  label: string;
  icon: typeof Stethoscope;
  tag: string;
  title: string;
  subtitle: string;
  description: string;
  bullets: string[];
}

const simulatedTabs: SimulatedTab[] = [
  {
    id: "clinical",
    label: "Tư duy lâm sàng & dịch tễ",
    icon: Stethoscope,
    tag: "Tình huống nhiều bước",
    title: "Rèn Luyện Tư Duy Lâm Sàng & Phản Ứng Dịch Tễ Thực Địa",
    subtitle: "Mô phỏng chân thực các tình huống tiếp nhận và xử trí ca bệnh cộng đồng",
    description:
      "Không dừng lại ở việc chọn một đáp án đúng, bạn đồng hành cùng ca bệnh qua từng giai đoạn: khai thác tiền sử dịch tễ, phát hiện dấu hiệu cảnh báo, lập kế hoạch can thiệp y tế cơ sở và truyền thông dự phòng nguy cơ bùng phát.",
    bullets: [
      "Kịch bản đa bước: diễn tiến người bệnh thay đổi theo từng quyết định xử trí",
      "Giải thích lý do đúng/sai dựa trên sinh lý bệnh học và dịch tễ học thực chứng",
      "Rèn tư duy phản xạ trước các tình huống cấp cứu và giám sát dịch bệnh phức tạp",
    ],
  },
  {
    id: "spaced-repetition",
    label: "Thẻ ghi nhớ thông minh",
    icon: Layers,
    tag: "Phương pháp chống quên khoa học",
    title: "Ghi Nhớ Y Khoa Dài Hạn, Ôn Lại Để Nhớ Lâu Hơn",
    subtitle: "Hệ thống tự động nhắc nhở đúng thời điểm phù hợp để ôn lại kiến thức",
    description:
      "Hàng nghìn định nghĩa dịch tễ, phác đồ điều trị của Bộ Y tế, số liệu dinh dưỡng và tiêu chuẩn an toàn lao động được số hóa thành các thẻ học nhanh. Hệ thống tự động phát hiện câu bạn hay quên để nhắc ôn lại.",
    bullets: [
      "Tự động chuyển câu trắc nghiệm làm sai thành thẻ nhớ cần củng cố",
      "Tối ưu hóa thời gian học: chỉ 15–20 phút mỗi ngày duy trì nhịp ôn luyện",
      "Theo dõi chuỗi ngày học liên tục và mức độ sẵn sàng cho kỳ thi quốc gia",
    ],
  },
  {
    id: "cbt-exam",
    label: "Thi thử trên máy tính theo phạm vi đề tài",
    icon: ClipboardCheck,
    tag: "Luyện cách làm bài và quản lý thời gian",
    title: "Phần Mềm Thi Thử Trắc Nghiệm Trên Máy Tính",
    subtitle: "Chuẩn bị tâm lý, kỹ năng phân bổ thời gian và làm quen áp lực phòng thi",
    description:
      "Bài thi thử giúp làm quen với cách làm bài trên máy tính với đồng hồ đếm ngược thời gian thực, tự động lưu bài làm và phân tích kết quả ngay sau khi nộp bài.",
    bullets: [
      "Đồng hồ đếm ngược từng giây, tự động thu bài và niêm phong kết quả khi hết giờ",
      "Báo cáo phân tích phổ điểm chi tiết từ câu hỏi lý thuyết đến xử lý ca bệnh",
      "Khóa hoàn toàn trợ lý giải đáp trong giờ thi nhằm bảo đảm tính nghiêm túc khảo thí",
    ],
  },
  {
    id: "ai-tutor",
    label: "Trợ lý giải đáp có trích dẫn",
    icon: BrainCircuit,
    tag: "Đối chiếu giáo trình Bộ Y tế",
    title: "Giải thích điều chưa hiểu, kèm tài liệu để đọc thêm",
    subtitle: "Hiểu sâu bản chất vấn đề, học có căn cứ và đối chiếu nguồn gốc",
    description:
      "Khi gặp câu hỏi khó hoặc phân vân giữa các đáp án, hệ thống phân tích cơ chế và tự động cung cấp đường dẫn mở đúng trang sách giáo khoa Đại học Y Hà Nội, Thông tư, Hướng dẫn điều trị của Bộ Y tế để bạn kiểm chứng đối chiếu.",
    bullets: [
      "Mở tài liệu được dẫn để đối chiếu với lời giải",
      "Gợi mở tư duy chẩn đoán, phân tích từng phương án giúp người học hiểu sâu bản chất",
      "Chỉ dùng cho việc học; không thay thế ý kiến chuyên môn khi xử trí người bệnh",
    ],
  },
];

const competencyGroups = [
  {
    num: 1,
    title: "Sức khỏe quần thể & Dịch tễ học",
    icon: ActivityIcon,
    desc: "Giám sát dịch tễ học thực địa, phát hiện và xử lý ổ dịch truyền nhiễm, ứng dụng phân tích chỉ số dịch tễ học trong can thiệp sức khỏe cộng đồng.",
    problems: "12 vấn đề cốt lõi",
    bloom: "Nhớ · Hiểu · Vận dụng · Phân tích",
  },
  {
    num: 2,
    title: "Cấp cứu ban đầu & Xử trí khẩn cấp",
    icon: HeartPulse,
    desc: "Nhận định dấu hiệu sinh tồn, xử trí ban đầu sốc phản vệ, ngộ độc cấp tính, suy hô hấp, tai nạn thương tích và ứng phó thảm họa y tế công cộng.",
    problems: "8 vấn đề cốt lõi",
    bloom: "Vận dụng · Xử trí cấp cứu",
  },
  {
    num: 3,
    title: "Dinh dưỡng & An toàn thực phẩm",
    icon: Salad,
    desc: "Đánh giá tình trạng dinh dưỡng quần thể, can thiệp suy dinh dưỡng, béo phì, điều tra vụ ngộ độc thực phẩm và giám sát an toàn vệ sinh thực phẩm.",
    problems: "6 vấn đề cốt lõi",
    bloom: "Hiểu · Đánh giá nguy cơ",
  },
  {
    num: 4,
    title: "Bệnh truyền nhiễm & Không lây nhiễm",
    icon: Microscope,
    desc: "Dự phòng và quản lý bệnh truyền nhiễm phổ biến (Sốt xuất huyết, Lao, Sốt rét, COVID-19) cùng các bệnh mạn tính không lây (Tăng huyết áp, Đái tháo đường).",
    problems: "10 vấn đề cốt lõi",
    bloom: "Nhớ · Hiểu · Vận dụng",
  },
  {
    num: 5,
    title: "Sức khỏe môi trường & Nghề nghiệp",
    icon: HardHat,
    desc: "Đánh giá tác động sức khỏe của ô nhiễm môi trường nước, không khí, chất thải y tế; nhận diện tác hại nghề nghiệp và dự phòng bệnh nghề nghiệp.",
    problems: "6 vấn đề cốt lõi",
    bloom: "Nhận diện · Dự phòng tác hại",
  },
  {
    num: 6,
    title: "Y tế công cộng & Y học gia đình",
    icon: HousePlus,
    desc: "Quản lý chương trình y tế tuyến xã/phường, lập kế hoạch y tế địa phương, chăm sóc sức khỏe ban đầu liên tục và toàn diện theo nguyên lý Y học gia đình.",
    problems: "5 vấn đề cốt lõi",
    bloom: "Phân tích · Quản lý can thiệp",
  },
  {
    num: 7,
    title: "Sức khỏe tâm thần & Nâng cao sức khỏe",
    icon: BrainCircuit,
    desc: "Nhận diện sớm các rối loạn tâm thần thường gặp ở cộng đồng (trầm cảm, lo âu), kỹ năng truyền thông giáo dục sức khỏe và can thiệp thay đổi hành vi.",
    problems: "4 vấn đề cốt lõi",
    bloom: "Hiểu · Tư vấn cộng đồng",
  },
  {
    num: 8,
    title: "Giao tiếp y khoa, Đạo đức & Pháp luật",
    icon: HeartHandshake,
    desc: "Kỹ năng tư vấn sức khỏe cho người bệnh và cộng đồng, đạo đức hành nghề y khoa, tuân thủ Luật Khám bệnh, chữa bệnh số 15/2023/QH15 và quy định Bộ Y tế.",
    problems: "3 vấn đề cốt lõi",
    bloom: "Đạo đức · Pháp lý y tế",
  },
];

function ActivityIcon(props: { size?: number; className?: string }) {
  return <MessagesSquare {...props} />;
}

export function Landing() {
  const actor = useActor();
  const start = actor ? roleHome(actor.role) : "/dang-nhap";
  const [activeTabId, setActiveTabId] = useState("clinical");

  const currentTab =
    simulatedTabs.find((t) => t.id === activeTabId) || simulatedTabs[0];

  return (
    <div className="portal-page-wrapper project-landing">
      <PortalHeader />

      <main id="main-content">
        {/* Hero Section: 1 Authenticated Vietnam HMU Photograph, Organic Wave Divider */}
        <AntigravityHero start={start} />

        {/* Chapter Quick Navigation */}
        <nav className="landing-chapter-nav" aria-label="Khám phá trang giới thiệu">
          <div className="project-container">
            <a href="#tong-quan-airc">Đề tài & AIRC</a>
            <a href="#chuan-nang-luc">8 Chuẩn năng lực</a>
            <a href="#trai-nghiem-hoc">Cách học và ôn tập</a>
            <a href="#kien-truc-rag">Cách đối chiếu tài liệu</a>
            <a href="#quy-trinh-tham-dinh">Thẩm định 2 vòng</a>
            <a href="#lo-trinh-de-tai">Lộ trình triển khai</a>
            <a href="#doi-tuong-su-dung">Đối tượng</a>
          </div>
        </nav>

        {/* Section 1: Research Proposal Overview & Institutional Context */}
        {/* Section 1: Institutional Research Overview, Legal Framework & Academic Verification */}
        <section id="tong-quan-airc" className="project-introduction project-container project-section">
          <ScrollReveal className="intro-section-header">
            <div className="institutional-meta-tag">
              <span className="meta-tag-bullet" />
              <span>ĐỀ TÀI NGHIÊN CỨU &amp; PHÁT TRIỂN CÔNG NGHỆ SỐ Y KHOA · TRỌNG ĐIỂM QUỐC GIA</span>
            </div>
            <h2>
              Hệ thống hóa toàn diện kiến thức Y học dự phòng,
              <br className="desktop-break" />
              vững vàng năng lực thực hành trước kỳ kiểm tra Quốc gia.
            </h2>
            <p className="intro-section-lead">
              Nền tảng số thông minh do Trung tâm AIRC nghiên cứu và phát triển, phối hợp chuyên môn sâu cùng Viện Đào tạo Y học dự phòng &amp; Y tế công cộng (Trường Đại học Y Hà Nội) — đồng hành cùng sinh viên và bác sĩ làm chủ 54 vấn đề sức khỏe cốt lõi theo phạm vi đề tài.
            </p>
          </ScrollReveal>

          {/* Unified National Metrics Registry Ledger (Thay thế 4 thẻ KPI pastel kiểu AI) */}
          <ScrollReveal>
            <div className="institutional-metrics-ledger" role="region" aria-label="Bảng thông số quy chuẩn nhiệm vụ y khoa">
              <div className="ledger-header-strip">
                <span className="ledger-title">QUY CHUẨN ĐÀO TẠO &amp; CHỈ SỐ NHIỆM VỤ Y KHOA</span>
                <span className="ledger-doc-ref">CĂN CỨ THEO QUYẾT ĐỊNH CỦA BỘ Y TẾ &amp; HỘI ĐỒNG Y KHOA QUỐC GIA</span>
              </div>
              <div className="ledger-cells-grid">
                <div className="ledger-cell">
                  <div className="ledger-cell-meta">
                    <span className="ledger-index">01</span>
                    <span className="ledger-status-tag">Ưu tiên BYT</span>
                  </div>
                  <div className="ledger-number">54</div>
                  <div className="ledger-label">Vấn đề sức khỏe cốt lõi</div>
                  <div className="ledger-desc">Phạm vi trọng tâm theo chuẩn năng lực cơ bản của Bác sĩ YHDP</div>
                </div>

                <div className="ledger-cell">
                  <div className="ledger-cell-meta">
                    <span className="ledger-index">02</span>
                    <span className="ledger-status-tag">Toàn diện</span>
                  </div>
                  <div className="ledger-number">08</div>
                  <div className="ledger-label">Lĩnh vực năng lực chuẩn</div>
                  <div className="ledger-desc">Bao quát từ giám sát dịch tễ, y tế môi trường đến quản lý sức khỏe cộng đồng</div>
                </div>

                <div className="ledger-cell">
                  <div className="ledger-cell-meta">
                    <span className="ledger-index">03</span>
                    <span className="ledger-status-tag">Chính thống</span>
                  </div>
                  <div className="ledger-number">Nguồn</div>
                  <div className="ledger-label">Tài liệu để đọc và đối chiếu</div>
                  <div className="ledger-desc">Đọc tài liệu được dẫn và kiểm tra nội dung liên quan với lời giải</div>
                </div>

                <div className="ledger-cell">
                  <div className="ledger-cell-meta">
                    <span className="ledger-index">04</span>
                    <span className="ledger-status-tag">Độc lập</span>
                  </div>
                  <div className="ledger-number">2 Vòng</div>
                  <div className="ledger-label">Thẩm định chuyên gia y khoa</div>
                  <div className="ledger-desc">Hội đồng phản biện kiểm duyệt mù nghiêm ngặt trước khi đưa vào ngân hàng ôn tập</div>
                </div>
              </div>
            </div>
          </ScrollReveal>

          {/* Institutional Dossier & Educational Framework (Thay thế 2 card đối xứng border-t-4 và callout xanh pastel của AI) */}
          <div className="institutional-dossier-grid">
            {/* Dossier Column 1: Legal Basis & Institutional Consortium */}
            <ScrollReveal className="dossier-column mandate-column">
              <div>
                <div className="dossier-column-header">
                  <span className="dossier-section-index">PHẦN I</span>
                  <span className="dossier-section-caption">CƠ SỞ PHÁP LÝ &amp; VỊ TRÍ HÀNH NGHỀ</span>
                </div>
                <h3 className="dossier-column-title">&ldquo;Lá chắn tiền tuyến&rdquo; trong hệ thống y tế công cộng và y học thực địa</h3>
                
                <div className="dossier-clauses">
                  <div className="dossier-clause">
                    <div className="clause-marker">§ 1.1</div>
                    <div className="clause-content">
                      <h4 className="clause-title">Căn cứ Luật Khám bệnh, chữa bệnh số 15/2023/QH15</h4>
                      <p className="clause-text">
                        Theo lộ trình của Hội đồng Y khoa Quốc gia, việc kiểm tra đánh giá năng lực hành nghề khám chữa bệnh là điều kiện tiên quyết và bắt buộc để được cấp giấy phép hành nghề bác sĩ trên toàn quốc.
                      </p>
                    </div>
                  </div>

                  <div className="dossier-clause">
                    <div className="clause-marker">§ 1.2</div>
                    <div className="clause-content">
                      <h4 className="clause-title">Sứ mệnh chức danh Bác sĩ Y học dự phòng</h4>
                      <p className="clause-text">
                        Giữ vai trò tiền tuyến trong giám sát dịch tễ học, dập dịch thực địa, kiểm soát an toàn vệ sinh thực phẩm, y tế môi trường - lao động và điều phối can thiệp sức khỏe quần thể tại cơ sở.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Khối Hợp tác chuyên môn liên viện - Trang trọng, chuẩn mực, TUYỆT ĐỐI KHÔNG RỚT DÒNG */}
                <div className="consortium-credentials-box">
                  <div className="credentials-label">ĐƠN VỊ PHÁT TRIỂN &amp; BẢO TRỢ CHUYÊN MÔN</div>
                  <div className="credentials-partners">
                    <div className="partner-record">
                      <span className="partner-role-badge">Đơn vị công nghệ</span>
                      <div className="partner-text">
                        <span className="partner-name">Trung tâm AIRC</span>
                        <span className="partner-duty">Nghiên cứu kiến trúc &amp; phát triển nền tảng số</span>
                      </div>
                    </div>
                    <div className="partner-record">
                      <span className="partner-role-badge">Bảo trợ học thuật</span>
                      <div className="partner-text">
                        <span className="partner-name">Viện Đào tạo Y học dự phòng &amp; Y tế công cộng</span>
                        <span className="partner-duty">Trường Đại học Y Hà Nội — Thẩm định &amp; chuẩn hóa chuyên môn</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="dossier-action-footer">
                <Link className="institutional-text-link" to="/ve-chung-toi">
                  <span>Tìm hiểu thêm về đề tài và sứ mệnh AIRC</span>
                  <ArrowRight size={15} />
                </Link>
              </div>
            </ScrollReveal>

            {/* Dossier Column 2: Target Cohorts & Educational Rigor Framework */}
            <ScrollReveal className="dossier-column framework-column">
              <div>
                <div className="dossier-column-header">
                  <span className="dossier-section-index">PHẦN II</span>
                  <span className="dossier-section-caption">ĐỐI TƯỢNG TRỌNG TÂM &amp; CHUẨN ĐẦU RA</span>
                </div>
                <h3 className="dossier-column-title">Học để thấu hiểu bản chất y lý · Tự tin bước vào phòng thi trắc nghiệm máy tính</h3>

                <div className="cohort-tracks-list">
                  <div className="cohort-track-item">
                    <div className="track-header">
                      <span className="track-step">NHÓM 01</span>
                      <h4 className="track-title">Sinh viên YHDP năm cuối chuẩn bị tốt nghiệp (Y6)</h4>
                    </div>
                    <p className="track-description">
                      Hệ thống hóa toàn diện khối kiến thức tích lũy qua 6 năm học, lấp đầy các khoảng trống chuyên khoa (Dịch tễ, Dinh dưỡng, Vệ sinh môi trường, Quản lý y tế) và tự tin bước vào kỳ thi tốt nghiệp.
                    </p>
                  </div>

                  <div className="cohort-track-item">
                    <div className="track-header">
                      <span className="track-step">NHÓM 02</span>
                      <h4 className="track-title">Bác sĩ YHDP tham gia kiểm tra năng lực Quốc gia</h4>
                    </div>
                    <p className="track-description">
                      Rèn luyện tư duy xử trí tình huống ca bệnh thực địa đa bước, làm quen với áp lực đồng hồ đếm ngược và giao diện thi trắc nghiệm trên máy tính để luyện cách phân bổ thời gian.
                    </p>
                  </div>
                </div>
              </div>

              {/* Khối Cam kết chất lượng học thuật - Thay thế hoàn toàn callout xanh pastel của AI */}
              <div className="academic-charter-box">
                <div className="charter-header">
                  <span className="charter-seal">CAM KẾT CHUYÊN MÔN</span>
                  <span className="charter-standard">BẢO CHỨNG Y VĂN</span>
                </div>
                <h4 className="charter-title">Trọng tâm 54 Vấn đề sức khỏe ưu tiên Quốc gia</h4>
                <p className="charter-body">
                  Toàn bộ nội dung học tập bám sát khung 54 vấn đề cốt lõi do Hội đồng Chuyên gia Y khoa xác định trong thuyết minh nhiệm vụ. Hệ thống hướng người học làm chủ nguyên lý bệnh sinh và xử trí cộng đồng thực chứng, kiên quyết loại bỏ hình thức học tủ hay ghi nhớ máy móc ngân hàng câu hỏi.
                </p>
              </div>
            </ScrollReveal>
          </div>
        </section>

        {/* Section 2: 8 Competency Groups Explorer */}
        <section id="chuan-nang-luc" className="competency-matrix-section">
          <div className="project-container">
            <ScrollReveal className="section-head-center">
              <span className="section-pill">Khung Chuẩn Năng Lực Quốc Gia</span>
              <h2>8 Nhóm Chuẩn Năng Lực Bác Sĩ Y Học Dự Phòng</h2>
              <p>
                Được xây dựng bám sát Khung chuẩn năng lực cơ bản của Bác sĩ Y học dự phòng ban hành theo Quyết định của Bộ Y tế, bảo đảm người học sẵn sàng cho cả kỳ thi sát hạch lẫn thực tiễn công tác y tế.
              </p>
            </ScrollReveal>

            <div className="comp-groups-grid">
              {competencyGroups.map((group) => {
                const IconComponent = group.icon;
                return (
                  <ScrollReveal key={group.num} className="comp-group-card">
                    <div className="comp-group-badge-num">0{group.num}</div>
                    <div className="comp-group-header">
                      <div className="comp-group-icon">
                        <IconComponent size={20} />
                      </div>
                      <h3 className="comp-group-title">{group.title}</h3>
                    </div>
                    <p className="comp-group-desc">{group.desc}</p>
                    <div className="comp-group-footer">
                      <span className="comp-group-pill">{group.problems}</span>
                      <span>Mức độ hiểu và vận dụng</span>
                    </div>
                  </ScrollReveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* Section 3: Innovative Learning Methods - 100% Simulated UI, Zero Extra Photos */}
        <section className="landing-tabs-section" id="trai-nghiem-hoc">
          <div className="project-container">
            <ScrollReveal className="section-head-center">
              <span className="section-pill">Đột phá Phương pháp</span>
              <h2>Học để Hiểu Bản Chất. Luyện để Vững Tay Nghề.</h2>
              <p>
                Trải nghiệm học tập hiện đại, kết nối liên hoàn giữa hỏi đáp từng bước, thẻ nhớ giãn cách và mô phỏng bài thi trên máy tính.
              </p>
            </ScrollReveal>

            {/* Tab Navigation */}
            <div className="landing-tabs-nav" role="tablist" aria-label="Phương pháp học tập">
              {simulatedTabs.map((tab) => {
                const isSelected = activeTabId === tab.id;
                const TabIcon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    className={`landing-tab-btn ${isSelected ? "active" : ""}`}
                    onClick={() => setActiveTabId(tab.id)}
                  >
                    {isSelected && (
                      <motion.div
                        layoutId="activeLandingTabBubble"
                        className="landing-tab-bubble"
                        transition={{ type: "spring", stiffness: 400, damping: 32 }}
                      />
                    )}
                    <TabIcon size={17} className="tab-icon" />
                    <span className="tab-label">{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Tab Panel Content: Text Left, Interactive Simulated UI Right */}
            <div className="landing-tab-content-panel">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentTab.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.28, ease: "easeOut" }}
                  className="landing-tab-grid"
                >
                  <div className="landing-tab-text">
                    <span className="tab-feature-tag">{currentTab.tag}</span>
                    <h3>{currentTab.title}</h3>
                    <p className="tab-feature-sub">{currentTab.subtitle}</p>
                    <p className="tab-feature-desc">{currentTab.description}</p>

                    <ul className="tab-feature-bullets">
                      {currentTab.bullets.map((b, idx) => (
                        <li key={idx}>
                          <CheckCircle2 size={16} className="bullet-icon" />
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>

                    <div className="tab-feature-action">
                      <Link to={start} className="btn-hero-primary" style={{ border: "1px solid #cbd5e1" }}>
                        <span>Trải nghiệm tính năng này</span>
                        <ArrowRight size={16} />
                      </Link>
                    </div>
                  </div>

                  {/* Right Side: Simulated Pure UI (No stock photos!) */}
                  <div className="landing-tab-visual">
                    <div className="simulated-ui-container">
                      <div className="sim-window-bar">
                        <div className="sim-window-dots">
                          <span />
                          <span />
                          <span />
                        </div>
                        <div className="sim-window-title">
                          <currentTab.icon size={13} />
                          <span>Mô phỏng giao diện · DocPrep YHDP</span>
                        </div>
                        <span style={{ fontSize: 10, color: "#94a3b8" }}>Bản quyền AIRC</span>
                      </div>

                      <div className="sim-window-body">
                        {currentTab.id === "clinical" && (
                          <div className="sim-case-flow">
                            <div className="sim-case-step-badge">
                              <span>Bước 1 / 3 · Khai thác dịch tễ học thực địa</span>
                            </div>
                            <div className="sim-case-vignette">
                              <strong>Tình huống:</strong> Tại xã X ghi nhận 5 ca sốt cao đột ngột, đau mỏi cơ và xuất huyết dưới da trong vòng 48 giờ. Là Bác sĩ Y học dự phòng phụ trách trạm, hành động ưu tiên đầu tiên của bạn là gì?
                            </div>
                            <div className="sim-case-options">
                              <div className="sim-case-opt">
                                <span className="sim-case-opt-letter">A</span>
                                <span>Kê đơn thuốc kháng sinh phổ rộng cho toàn bộ người tiếp xúc gần</span>
                              </div>
                              <div className="sim-case-opt selected">
                                <span className="sim-case-opt-letter">B</span>
                                <span>Lập phiếu điều tra dịch tễ, khoanh vùng ổ dịch và báo cáo khẩn về Trung tâm Y tế huyện</span>
                              </div>
                              <div className="sim-case-opt">
                                <span className="sim-case-opt-letter">C</span>
                                <span>Chờ kết quả xét nghiệm huyết thanh khẳng định sau 7 ngày rồi mới xử lý</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {currentTab.id === "spaced-repetition" && (
                          <div className="sim-card-box">
                            <div className="sim-card-meta">
                              <span>Thẻ YHDP · Dịch tễ học bệnh sốt rét</span>
                              <span>Độ vững: 94%</span>
                            </div>
                            <div className="sim-card-prompt">
                              &ldquo;Chỉ số API (Annual Parasite Incidence) trong giám sát dịch tễ học sốt rét được tính như thế nào?&rdquo;
                            </div>
                            <div className="sim-card-answer-reveal">
                              <strong>Công thức chuẩn BYT:</strong>
                              <br />
                              API = (Số ca xét nghiệm dương tính KSTSR trong năm / Dân số vùng nguy cơ) × 1.000 dân.
                            </div>
                            <div className="sim-card-sm2-pills">
                              <span className="sim-card-sm2-pill easy">Dễ (Ôn sau 14 ngày)</span>
                              <span className="sim-card-sm2-pill good">Tốt (Ôn sau 6 ngày)</span>
                              <span className="sim-card-sm2-pill hard">Khó (Ôn lại sau 1 ngày)</span>
                            </div>
                          </div>
                        )}

                        {currentTab.id === "cbt-exam" && (
                          <div className="sim-cbt-box">
                            <div className="sim-cbt-header">
                              <div className="sim-cbt-timer">
                                <Clock size={15} />
                                <span>118:45</span>
                              </div>
                              <div className="sim-cbt-save-status">
                                <CheckCircle2 size={14} />
                                <span>Autosave: Đã lưu 38/40 câu</span>
                              </div>
                            </div>
                            <div className="sim-cbt-stepper">
                              {[...Array(24)].map((_, i) => (
                                <div
                                  key={i}
                                  className={`sim-cbt-dot ${
                                    i === 14
                                      ? "current"
                                      : i === 6
                                      ? "flagged"
                                      : i < 18
                                      ? "done"
                                      : ""
                                  }`}
                                >
                                  {i + 1}
                                </div>
                              ))}
                            </div>
                            <div className="sim-cbt-bloom-summary">
                              <div className="sim-cbt-bloom-item">
                                <strong>86%</strong>
                                <span>Mức 1-2 (Nhớ/Hiểu)</span>
                              </div>
                              <div className="sim-cbt-bloom-item">
                                <strong>74%</strong>
                                <span>Mức 3-4 (Vận dụng)</span>
                              </div>
                              <div className="sim-cbt-bloom-item">
                                <strong>Phân tích</strong>
                                <span>Mức độ hiểu và vận dụng</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {currentTab.id === "ai-tutor" && (
                          <div className="sim-chat-thread">
                            <div className="sim-chat-msg user">
                              Thưa Hỏi đáp học tập, tại sao trong xử trí ổ dịch Sốt xuất huyết Dengue, chỉ số BI &gt;= 30 lại là ngưỡng bắt đầu phun hóa chất diệt muỗi trưởng thành?
                            </div>
                            <div className="sim-chat-msg tutor">
                              Chào bạn! Chỉ số BI (Breteau Index) &gt;= 30 phản ánh mật độ bọ gậy/lăng quăng Aedes aegypti tại các dụng cụ chứa nước đã vượt ngưỡng an toàn dịch tễ. Mật độ này kết hợp với có ca bệnh chỉ điểm chứng tỏ nguy cơ bùng phát dịch thứ phát rất cao, do đó Bộ Y tế quy định phải phun hóa chất diệt muỗi dập dịch diện rộng kết hợp diệt bọ gậy.
                              <div className="sim-chat-cite-box">
                                <BookOpenCheck size={14} />
                                <span>Nguồn: Quyết định số 3711/QĐ-BYT - Hướng dẫn giám sát và phòng chống bệnh Sốt xuất huyết Dengue, Bộ Y tế.</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </section>

        {/* Section 4: Architecture Pipeline (tìm và đối chiếu tài liệu & Knowledge Graph) */}
        <section id="kien-truc-rag" className="architecture-section">
          <div className="project-container">
            <ScrollReveal className="section-head-center">
              <span className="section-pill">Học có căn cứ</span>
              <h2>Bạn có thể kiểm tra lời giải như thế nào?</h2>
              <p>
                Bạn không cần biết về công nghệ để sử dụng. Khi đọc lời giải, hãy mở tài liệu được dẫn, so sánh với kiến thức đã học và ghi lại những điểm cần hỏi giảng viên.
              </p>
            </ScrollReveal>

            <div className="arch-cards-row">
              <ScrollReveal className="arch-layer-card">
                <span className="arch-layer-tag">01 · ĐỌC TÀI LIỆU</span>
                <h4>Tìm lại kiến thức trong giáo trình</h4>
                <p>
                  Dự án hướng tới tập hợp tài liệu phù hợp với nội dung ôn tập. Khi có trích dẫn, bạn có thể mở phần liên quan để đọc lại và đối chiếu với lời giải.
                </p>
              </ScrollReveal>

              <ScrollReveal className="arch-layer-card">
                <span className="arch-layer-tag">02 · HIỂU MỐI LIÊN QUAN</span>
                <h4>Nối kiến thức với tình huống học tập</h4>
                <p>
                  Xem yếu tố nguy cơ, dấu hiệu, cách đánh giá và biện pháp dự phòng liên quan với nhau ra sao, thay vì học từng ý rời rạc.
                </p>
              </ScrollReveal>

              <ScrollReveal className="arch-layer-card">
                <span className="arch-layer-tag">03 · KIỂM TRA LỜI GIẢI</span>
                <h4>Hỏi lại khi chưa rõ</h4>
                <p>
                  Phần hỏi đáp hỗ trợ giải thích bài học và vẫn có thể sai. Hãy kiểm tra nguồn, báo nội dung chưa đúng và hỏi giảng viên khi cần. Phần này không dùng để quyết định xử trí người bệnh.
                </p>
              </ScrollReveal>

              <ScrollReveal className="arch-layer-card">
                <span className="arch-layer-tag">04 · CHỌN PHẦN CẦN ÔN</span>
                <h4>Biết mình cần học thêm ở đâu</h4>
                <p>
                  Xem lại câu làm sai và kết quả theo chủ đề để chọn nội dung ôn tiếp. Kết quả thi thử giúp bạn điều chỉnh việc học, không thay thế đánh giá năng lực hành nghề.
                </p>
              </ScrollReveal>
            </div>
          </div>
        </section>

        {/* Section 5: 2-Round Expert Quality Review Pipeline */}
        <section id="quy-trinh-tham-dinh" className="expert-review-section">
          <div className="project-container">
            <ScrollReveal className="section-head-center">
              <span className="section-pill">Kiểm Soát Chuyên Môn</span>
              <h2>Quy Trình Thẩm Định 2 Vòng Độc Lập Của Hội Đồng Chuyên Gia</h2>
              <p>
                Công nghệ AI chỉ đóng vai trò hỗ trợ; mọi câu hỏi và nội dung đưa vào ngân hàng đề thi chính thức đều phải vượt qua 2 vòng thẩm định mù độc lập của các chuyên gia y tế.
              </p>
            </ScrollReveal>

            <div className="expert-review-grid">
              <ScrollReveal className="review-step-card">
                <div className="review-step-num">VÒNG 1 · BIÊN SOẠN & RÀ SOÁT</div>
                <h3>Biên Soạn Gắn Với 54 Vấn Đề Cốt Lõi</h3>
                <p>
                  Chuyên gia y học dự phòng biên soạn câu hỏi bám sát mục tiêu năng lực, ghi rõ đáp án, giải thích chi tiết và trích dẫn trang sách giáo khoa tham chiếu.
                </p>
              </ScrollReveal>

              <ScrollReveal className="review-step-card">
                <div className="review-step-num">VÒNG 2 · THẨM ĐỊNH NỘI DUNG</div>
                <h3>Thẩm Định Y Học Chứng Cứ Vòng 1</h3>
                <p>
                  Chuyên gia thứ nhất kiểm định tính chính xác chuyên môn, đối chiếu hướng dẫn điều trị hiện hành của Bộ Y tế và đánh giá độ hợp lý của các phương án nhiễu.
                </p>
              </ScrollReveal>

              <ScrollReveal className="review-step-card">
                <div className="review-step-num">VÒNG 3 · KIỂM CHUẨN ĐỘC LẬP</div>
                <h3>Thẩm Định Độc Lập Vòng 2 (Mù Đôi)</h3>
                <p>
                  Chuyên gia thứ hai đánh giá độc lập hoàn toàn, không biết kết quả vòng 1, nhằm kiểm định độ khó, độ phân cách và mức độ phù hợp với kỳ thi quốc gia.
                </p>
              </ScrollReveal>

              <ScrollReveal className="review-step-card">
                <div className="review-step-num">VÒNG 4 · XUẤT BẢN NGÂN HÀNG ĐỀ</div>
                <h3>Phê duyệt câu hỏi cho bài thi thử</h3>
                <p>
                  Chỉ những câu hỏi đạt đồng thuận tuyệt đối của cả 2 chuyên gia độc lập mới được gắn nhãn &ldquo;Đã duyệt&rdquo; và đưa vào ngân hàng khảo thí chính thức.
                </p>
              </ScrollReveal>
            </div>
          </div>
        </section>

        {/* Section 6: Research Roadmap */}
        <section id="lo-trinh-de-tai" className="project-roadmap project-container project-section">
          <div className="project-section-heading">
            <div>
              <span className="section-pill">Kế Hoạch Khoa Học</span>
              <h2>Lộ Trình Nghiên Cứu & Triển Khai Thực Tiễn</h2>
              <p>
                Được xây dựng theo đúng kế hoạch triển khai nêu trong thuyết minh nhiệm vụ khoa học công nghệ, chia thành 2 giai đoạn kế thừa và kiểm chứng chặt chẽ.
              </p>
            </div>
            <Link to="/nghien-cuu" className="project-text-link">
              Xem báo cáo định hướng nghiên cứu <ArrowRight size={17} />
            </Link>
          </div>

          <div className="roadmap-lines">
            <article>
              <div>
                <span className="section-pill" style={{ background: "#e0f2fe", color: "#0369a1" }}>Giai đoạn 1</span>
                <p>10/2026 – 04/2027 · Đang triển khai</p>
              </div>
              <h3>Chatbot Ôn Thi Có Kiểm Soát & Kho Dữ Liệu Chuẩn Hóa</h3>
              <p>
                Hoàn thiện hệ sinh thái Chatbot AI có trích dẫn nguồn, chuẩn hóa 54 vấn đề cốt lõi YHDP, thẩm định tối thiểu 300 câu hỏi trọng tâm và thử nghiệm giao diện với sinh viên năm cuối.
              </p>
            </article>

            <article>
              <div>
                <span className="section-pill" style={{ background: "#dcfce7", color: "#15803d" }}>Giai đoạn 2</span>
                <p>04/2027 – 12/2028 · Kế hoạch mở rộng</p>
              </div>
              <h3>Nền Tảng Số Tích Hợp & Nghiên Cứu Hiệu Quả Can Thiệp</h3>
              <p>
                Tích hợp toàn diện ngân hàng 1.000–1.500 câu hỏi, mở rộng thi thử trên máy tính, triển khai nghiên cứu can thiệp bán thực nghiệm đánh giá hiệu quả học tập và khả năng sử dụng và duy trì tại cơ sở đào tạo.
              </p>
            </article>
          </div>
        </section>

        {/* Section 7: Audience Ecosystem */}
        <section id="doi-tuong-su-dung" className="landing-audience-revamped">
          <div className="portal-container">
            <div className="audience-card-wrapper">
              <div className="audience-header">
                <GraduationCap size={38} className="audience-icon" />
                <h2>Thiết Kế May Đo Cho Hệ Sinh Thái Đào Tạo Y Khoa</h2>
                <p>
                  Mỗi vai trò trong hệ thống được cung cấp một không gian thao tác riêng biệt, bảo đảm tính phân quyền và phục vụ trọn vẹn tiến trình học tập - kiểm định.
                </p>
              </div>

              <div className="audience-roles-grid">
                <div className="role-chip-card">
                  <div className="role-icon">
                    <GraduationCap size={24} />
                  </div>
                  <h4>Sinh viên YHDP Năm Cuối</h4>
                  <p>Hệ thống hóa kiến thức trước kỳ thi tốt nghiệp và chuẩn bị cho kỳ kiểm tra đánh giá năng lực quốc gia.</p>
                </div>

                <div className="role-chip-card">
                  <div className="role-icon">
                    <Stethoscope size={24} />
                  </div>
                  <h4>Bác sĩ YHDP Mới Tốt Nghiệp</h4>
                  <p>Rèn luyện tư duy biện luận lâm sàng, cập nhật hướng dẫn điều trị mới nhất của Bộ Y tế khi bắt đầu hành nghề.</p>
                </div>

                <div className="role-chip-card">
                  <div className="role-icon">
                    <FileCheck2 size={24} />
                  </div>
                  <h4>Giảng viên & Chuyên gia Thẩm định</h4>
                  <p>Biên soạn, kiểm duyệt câu hỏi qua 2 vòng độc lập và theo dõi phổ điểm, mức độ sẵn sàng của học viên theo mức độ hiểu và vận dụng.</p>
                </div>

                <div className="role-chip-card">
                  <div className="role-icon">
                    <LineChart size={24} />
                  </div>
                  <h4>Cán bộ Khảo thí & Quản lý</h4>
                  <p>Theo dõi báo cáo tiến độ, giám sát độ bao phủ 54 vấn đề cốt lõi và đánh giá tính an toàn tuân thủ của nền tảng.</p>
                </div>
              </div>

              <div className="audience-action-wrap">
                <Link to={start} className="btn-hero-primary" style={{ border: "1px solid #cbd5e1" }}>
                  <span>Vào không gian trải nghiệm</span>
                  <ArrowRight size={17} />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Section 8: Closing CTA */}
        <section className="project-closing">
          <div className="project-container">
            <div>
              <h2>
                Bắt đầu từ một mục tiêu rõ ràng.
                <br />
                Đồng hành cùng trí tuệ nhân tạo có kiểm chứng.
              </h2>
              <p>
                Khám phá không gian ôn tập Y học dự phòng ngay hôm nay với dữ liệu minh họa bám sát thuyết minh đề tài.
              </p>
            </div>
            <Link to={start} className="project-button project-button-light">
              Trải nghiệm nền tảng ngay <ArrowRight size={18} />
            </Link>
          </div>
        </section>
      </main>

      <PortalFooter />
    </div>
  );
}
