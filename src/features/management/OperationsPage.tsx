import {
  BarChart3,
  ChevronRight,
  FileSpreadsheet,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

export function OperationsPage() {
  return (
    <div className="operations-page">
      <header className="operations-header">
        <h1>Vận hành hệ thống</h1>
        <p className="operations-desc">
          Quản lý tài khoản và theo dõi hoạt động đào tạo.
        </p>
      </header>

      <section
        className="staff-import-action"
        aria-labelledby="staff-import-title"
      >
        <FileSpreadsheet size={26} aria-hidden="true" />
        <h2 id="staff-import-title">Cấp tài khoản người học</h2>
        <p>Nhập danh sách từ tệp CSV, kiểm tra và cấp mã kích hoạt.</p>
        <Link className="staff-primary-action" to="/quan-tri/tai-khoan">
          Nhập danh sách CSV
          <ChevronRight size={17} aria-hidden="true" />
        </Link>
      </section>

      <section
        className="staff-report-links"
        aria-labelledby="staff-reports-title"
      >
        <h2 id="staff-reports-title">Theo dõi và báo cáo</h2>
        <div className="operations-action-list">
          <Link className="op-action-item" to="/quan-ly">
            <div className="op-action-icon">
              <BarChart3 size={18} />
            </div>
            <div className="op-action-body">
              <strong>Báo cáo tổng quan</strong>
              <span>Hoạt động học tập và kết quả từng học phần</span>
            </div>
            <ChevronRight size={16} className="op-action-arrow" />
          </Link>
          <Link className="op-action-item safety-action" to="/quan-ly/an-toan">
            <div className="op-action-icon">
              <ShieldCheck size={20} />
            </div>
            <div className="op-action-body">
              <strong>An toàn và tuân thủ</strong>
              <span>Chất lượng câu trả lời và tình trạng vận hành</span>
            </div>
            <ChevronRight size={16} className="op-action-arrow" />
          </Link>
        </div>
      </section>
    </div>
  );
}
