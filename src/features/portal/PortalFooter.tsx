import { Link } from "react-router-dom";
import { ArrowUp } from "lucide-react";
import { BrandLogo } from "../../components/BrandLogo";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";

const groups = [
  {
    title: "Dự án",
    links: [
      ["/ve-chung-toi", "Về dự án"],
      ["/nghien-cuu", "Định hướng nghiên cứu"],
      ["/tinh-nang", "Cách nền tảng hỗ trợ học"],
    ],
  },
  {
    title: "Người sử dụng",
    links: [
      ["/hoc-vien", "Dành cho người học"],
      ["/giang-vien-gioi-thieu", "Dành cho giảng viên"],
      ["/hoc-cung-ai", "Cách sử dụng phần hỏi đáp"],
      ["/faq", "Câu hỏi thường gặp"],
      ["/lien-he", "Liên hệ"],
    ],
  },
  {
    title: "Thông tin sử dụng",
    links: [
      ["/quyen-rieng-tu", "Quyền riêng tư"],
      ["/dieu-khoan", "Điều kiện sử dụng"],
      ["/cookie", "Bộ nhớ trình duyệt"],
      ["/bao-mat", "An toàn dữ liệu"],
      ["/tiep-can", "Khả năng tiếp cận"],
    ],
  },
];

export function PortalFooter() {
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      // Chỉ hiện khi người dùng lướt xuống dưới (vượt quá 350px)
      setShowScrollTop(window.scrollY > 350);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  };

  return (
    <footer className="project-footer" aria-label="Chân trang">
      <div className="project-container">
        <div className="project-footer-top">
          <div className="project-footer-about">
            <BrandLogo subtitle="Hỗ trợ ôn thi bác sĩ Y học dự phòng" />
            <p>
              Nền tảng số tích hợp AI hỗ trợ ôn thi năng lực hành nghề bác sĩ Y
              học dự phòng tại Việt Nam.
            </p>
            <p className="project-footer-status">
              Đang phát triển · Bản trải nghiệm giao diện
            </p>
          </div>
          {groups.map((group) => (
            <nav key={group.title} aria-label={group.title}>
              <h2>{group.title}</h2>
              {group.links.map(([to, label]) => (
                <Link to={to} key={to}>
                  {label}
                </Link>
              ))}
            </nav>
          ))}
        </div>
        <div className="project-footer-bottom">
          <p>© 2026 DocPrep YHDP · Phục vụ học tập và nghiên cứu.</p>
          <span>Không thay thế quyết định chuyên môn y khoa.</span>
        </div>
      </div>

      {/* Nút Cuộn về đầu trang nổi cố định ở góc dưới bên phải màn hình khi lướt xuống */}
      <AnimatePresence>
        {showScrollTop && (
          <motion.button
            type="button"
            className="portal-back-to-top-fab"
            aria-label="Về đầu trang"
            title="Cuộn về đầu trang"
            onClick={scrollToTop}
            initial={{ opacity: 0, scale: 0.7, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.7, y: 16 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
          >
            <ArrowUp size={20} />
          </motion.button>
        )}
      </AnimatePresence>
    </footer>
  );
}
