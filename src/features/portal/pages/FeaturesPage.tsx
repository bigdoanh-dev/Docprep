import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Home,
  Layers,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { LearningPreview } from "../LearningPreview";
import { ScrollReveal } from "../../../components/ScrollReveal";

export function FeaturesPage() {
  return (
    <article className="project-feature-page modern-feature-page">
      {/* Top Banner / Editorial Header */}
      <header className="features-page-header">
        <div className="project-container">
          <nav aria-label="Đường dẫn trang" className="modern-breadcrumbs">
            <Link to="/gioi-thieu" className="breadcrumb-home">
              <Home size={14} />
              <span>Trang chủ</span>
            </Link>
            <ChevronRight size={13} className="breadcrumb-separator" />
            <span className="breadcrumb-current">Tính năng nền tảng</span>
          </nav>

          <div className="features-hero-content">
            <div className="portal-hero-badge">
              <Sparkles size={14} />
              <span>HỆ SINH THÁI TÍNH NĂNG · DOCPREP YHDP</span>
            </div>

            <h1 className="features-main-heading">
              Các hoạt động học tập,
              <br />
              cùng một hướng ôn luyện chuyên sâu.
            </h1>

            <p className="features-sub-heading">
              Hệ thống kết nối liền hoàn giữa hỏi đáp có trích dẫn giáo trình, luyện câu hỏi theo chuẩn năng lực, ôn thẻ ghi nhớ chống quên và thi thử trắc nghiệm trên máy tính theo phạm vi đề tài dành riêng cho Bác sĩ Y học dự phòng.
            </p>
          </div>
        </div>
      </header>

      {/* Interactive Workbench Section */}
      <section className="project-container features-preview-section">
        <LearningPreview />
      </section>

      {/* 4 Core Pillars Grid */}
      <section className="project-container project-section" id="lo-trinh-tinh-nang">
        <ScrollReveal className="section-head-center">
          <span className="section-pill">Bốn Trụ Cột Năng Lực</span>
          <h2>Từ Một Thắc Mắc Đến Một Lần Khắc Sâu Kiến Thức</h2>
          <p>
            Mỗi thao tác trên hệ thống đều hướng về một mục tiêu: giúp người học nắm chắc cơ chế sinh bệnh và phản xạ dịch tễ học thay vì chỉ nhớ máy móc một đáp án.
          </p>
        </ScrollReveal>

        <div className="feature-pillars-grid">
          <ScrollReveal className="pillar-feature-card">
            <div className="pillar-icon-box">
              <BrainCircuit size={24} />
            </div>
            <div className="pillar-tag">ĐỐI CHIẾU Y VĂN CHÍNH THỐNG</div>
            <h3>Trợ Lý Giải Đáp Có Đối Chiếu Giáo Trình</h3>
            <p>
              Giải thích nguyên lý sinh lý bệnh và dịch tễ học kèm đường dẫn mở trực tiếp sách giáo khoa Đại học Y Hà Nội, Hướng dẫn chẩn đoán điều trị của Bộ Y tế.
            </p>
            <ul className="pillar-list">
              <li><CheckCircle2 size={14} /> Đọc tài liệu được dẫn để kiểm tra lời giải</li>
              <li><CheckCircle2 size={14} /> Phân tích cặn kẽ vì sao đúng, vì sao chưa phù hợp</li>
              <li><CheckCircle2 size={14} /> Bảo đảm cơ sở học thuật, không suy diễn thông tin</li>
            </ul>
          </ScrollReveal>

          <ScrollReveal className="pillar-feature-card">
            <div className="pillar-icon-box">
              <BookOpen size={24} />
            </div>
            <div className="pillar-tag">54 VẤN ĐỀ CỐT LÕI</div>
            <h3>Ngân Hàng Câu Hỏi Thẩm Định 2 Vòng</h3>
            <p>
              Bao trọn 8 nhóm chuẩn năng lực cơ bản của BSYHDP: từ giám sát dịch tễ, an toàn thực phẩm, y tế lao động đến sơ cấp cứu ban đầu tại trạm y tế.
            </p>
            <ul className="pillar-list">
              <li><CheckCircle2 size={14} /> Hai vòng chuyên gia y khoa duyệt độc lập</li>
              <li><CheckCircle2 size={14} /> Phân cấp câu hỏi từ nhớ lý thuyết đến xử trí thực địa</li>
              <li><CheckCircle2 size={14} /> Kịch bản đa bước xử trí tình huống thực địa</li>
            </ul>
          </ScrollReveal>

          <ScrollReveal className="pillar-feature-card">
            <div className="pillar-icon-box">
              <Layers size={24} />
            </div>
            <div className="pillar-tag">PHƯƠNG PHÁP GHI NHỚ DÀI HẠN</div>
            <h3>Thẻ Ghi Nhớ Thông Minh (Chống Quên)</h3>
            <p>
              Tự động phát hiện các câu làm sai hoặc kiến thức còn yếu để chuyển thành thẻ ôn tập. Hệ thống nhắc ôn đúng thời điểm vàng trước khi bị quên lãng.
            </p>
            <ul className="pillar-list">
              <li><CheckCircle2 size={14} /> Chu kỳ nhắc nhở khoa học, chống quên kiến thức</li>
              <li><CheckCircle2 size={14} /> Duy trì nhịp học đều đặn mỗi ngày</li>
              <li><CheckCircle2 size={14} /> Tiết kiệm tối đa thời gian ôn lại lý thuyết</li>
            </ul>
          </ScrollReveal>

          <ScrollReveal className="pillar-feature-card">
            <div className="pillar-icon-box">
              <ClipboardCheck size={24} />
            </div>
            <div className="pillar-tag">THI THỬ TRÊN MÁY TÍNH</div>
            <h3>Mô Phỏng Phòng Thi Quốc Gia</h3>
            <p>
              Trải nghiệm bài thi trắc nghiệm trên máy tính với bộ đếm giờ thời gian thực, tự động lưu bài liên tục và phân tích kết quả ngay sau khi nộp bài.
            </p>
            <ul className="pillar-list">
              <li><CheckCircle2 size={14} /> Tự động thu bài và khóa trợ lý giải đáp khi thi</li>
              <li><CheckCircle2 size={14} /> Đánh dấu cờ (flag) các câu phân vân rà soát</li>
              <li><CheckCircle2 size={14} /> Báo cáo phổ điểm phân tích từ lý thuyết đến ca bệnh</li>
            </ul>
          </ScrollReveal>
        </div>
      </section>

      {/* Technical Status & Transparency Section */}
      <section className="project-feature-status modern-status-section">
        <div className="project-container">
          <div className="status-header-center">
            <ShieldCheck size={36} className="status-main-icon" />
            <h2>Minh Bạch Về Trạng Thái Phát Triển Của Nền Tảng</h2>
            <p>
              Đề tài được phát triển theo lộ trình khoa học của AIRC, phân định rõ ràng giữa các tính năng có thể thử nghiệm ngay và các cấu phần cần kết nối máy chủ.
            </p>
          </div>

          <div className="modern-status-cards-grid">
            <div className="status-tier-card tier-ready">
              <div className="tier-header">
                <span className="tier-pill ready">Có thể trải nghiệm ngay</span>
                <h4>Thử học bằng dữ liệu mẫu</h4>
              </div>
              <p>
                Trải nghiệm toàn bộ các luồng học tập: luyện tập 8 nhóm năng lực, hỏi đáp có trích dẫn giáo trình, ôn thẻ ghi nhớ chống quên, làm bài thi thử trắc nghiệm máy tính và phân tích kết quả lưu trên trình duyệt mà không cần tài khoản.
              </p>
            </div>

            <div className="status-tier-card tier-server">
              <div className="tier-header">
                <span className="tier-pill server">Đồng bộ máy chủ</span>
                <h4>Tài Khoản & Quản Lý Đào Tạo</h4>
              </div>
              <p>
                Xác thực phân quyền theo vai trò (người học, giảng viên, hội đồng thẩm định, cán bộ quản lý), lưu trữ lịch sử thi liên thiết bị và quản lý lớp học trực tuyến.
              </p>
            </div>

            <div className="status-tier-card tier-research">
              <div className="tier-header">
                <span className="tier-pill research">Nghiên cứu kiểm định</span>
                <h4>Đánh Giá Hiệu Quả & Nghiệm Thu</h4>
              </div>
              <p>
                Nghiên cứu can thiệp bán thực nghiệm đánh giá mức độ cải thiện điểm số và khả năng áp dụng và duy trì trong đào tạo tại các cơ sở đào tạo y khoa.
              </p>
            </div>
          </div>

          <div className="status-cta-wrapper">
            <Link className="btn-hero-primary" to="/dang-nhap" style={{ border: "1px solid #cbd5e1" }}>
              <span>Vào không gian trải nghiệm học tập</span>
              <ArrowRight size={17} />
            </Link>
          </div>
        </div>
      </section>
    </article>
  );
}
