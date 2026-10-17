import { roleHome, useActor } from "../../../app/identity";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Search, ArrowRight } from "lucide-react";
const faqs = [
  {
    question: "Dự án tập trung phục vụ ai?",
    answer:
      "Trọng tâm là sinh viên Y học dự phòng năm cuối và bác sĩ YHDP mới tốt nghiệp chuẩn bị ôn thi năng lực hành nghề. Mở rộng sang chuyên ngành khác là định hướng, chưa phải các chương trình đang mở trên nền tảng.",
  },
  {
    question: "Đây có phải nền tảng tổ chức kỳ kiểm tra hành nghề chính thức?",
    answer:
      "Không. DocPrep YHDP hỗ trợ ôn luyện và nghiên cứu phát triển công cụ học tập. Bài thi thử không cấp chứng chỉ hành nghề, không thay thế kỳ kiểm tra chính thức và không bảo đảm kết quả thi.",
  },
  {
    question: "Con số 54 vấn đề cốt lõi có nghĩa là đã đủ học liệu?",
    answer:
      "Đó là phạm vi mục tiêu theo thuyết minh. Học liệu và câu hỏi cần được xây dựng, liên kết nguồn và thẩm định. Một mục tiêu bao phủ không đồng nghĩa mọi chủ đề đã có đầy đủ nội dung trong bản trải nghiệm.",
  },
  {
    question: "Nguồn học liệu và câu hỏi được kiểm soát thế nào?",
    answer:
      "Định hướng dự án là rà soát tài liệu phù hợp, gắn nội dung với năng lực và tổ chức thẩm định chuyên gia. Câu dành cho đề thi thử phải thuộc nhóm được phê duyệt qua hai vòng theo quy trình đề xuất. Nội dung minh họa có nhãn minh họa, chưa thẩm định.",
  },
  {
    question: "AI có thể trả lời sai dù có nguồn không?",
    answer:
      "Có. Trích dẫn giúp kiểm chứng nhưng không loại bỏ hoàn toàn nguy cơ diễn giải sai hoặc nguồn chưa hỗ trợ kết luận. Hãy mở đoạn được dẫn, kiểm tra lập luận và báo lại nội dung chưa phù hợp. Hệ thống cần nêu giới hạn khi thiếu căn cứ.",
  },
  {
    question: "Tôi có thể dùng câu trả lời cho người bệnh thực tế không?",
    answer:
      "Nền tảng phục vụ học tập. Không dùng câu trả lời để kê đơn, chẩn đoán hay quyết định xử trí người bệnh thực tế. Không nhập dữ liệu có thể nhận diện người bệnh vào phần thử giao diện hoặc câu hỏi học tập.",
  },
  {
    question: "Bản trải nghiệm có kết nối hệ thống thật không?",
    answer:
      "Chế độ trải nghiệm dùng dữ liệu mẫu và cập nhật trạng thái trên trình duyệt, không kết nối hệ thống thật. Chế độ kết nối hệ thống là luồng riêng, cần có máy chủ và tài khoản tương ứng.",
  },
  {
    question: "Đăng nhập Google và Apple đã hoạt động chưa?",
    answer:
      "Ứng dụng hiện dùng mã kích hoạt cho người học và email cùng mật khẩu cho cán bộ. Không có đăng nhập Google hoặc Apple. Chọn Trải nghiệm để thử bằng dữ liệu mẫu.",
  },
  {
    question: "Tại sao tiến độ trải nghiệm không xuất hiện trên thiết bị khác?",
    answer:
      "Dữ liệu mẫu lưu trên trình duyệt và thiết bị đang dùng. Xóa bộ nhớ trang, dùng chế độ riêng tư hoặc đổi thiết bị có thể đặt lại tiến độ. Đồng bộ dữ liệu thật là một phần của hệ thống khi được triển khai.",
  },
  {
    question: "Các kết quả nghiên cứu đã được công bố ở đây chưa?",
    answer:
      "Chưa. Số liệu minh họa trên giao diện không phải bằng chứng về hiệu quả học tập, độ chính xác của AI hoặc kết quả thí điểm.",
  },
];
export function FaqPage() {
  const actor = useActor();
  const [search, setSearch] = useState("");
  const [opened, setOpened] = useState<string | null>(faqs[0].question);
  const fold = (value: string) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/đ/g, "d");
  const filtered = faqs.filter((faq) =>
    fold(faq.question + faq.answer).includes(fold(search)),
  );
  return (
    <article className="project-faq project-container">
      <header className="editorial-heading">
        <nav aria-label="Đường dẫn trang">
          <Link to="/gioi-thieu">Giới thiệu dự án</Link>
          <span>/</span>
          <span>Câu hỏi thường gặp</span>
        </nav>
        <h1>Câu hỏi thường gặp</h1>
        <p>
          Phạm vi dự án, cách sử dụng phần hỏi đáp, học liệu và dữ liệu trong
          bản trải nghiệm.
        </p>
      </header>
      <label className="project-faq-search">
        <Search size={21} />
        <input
          aria-label="Tìm câu hỏi thường gặp"
          placeholder="Tìm nội dung bạn cần…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <div className="project-faq-list">
        {filtered.map((faq) => {
          const id = `faq-${faqs.indexOf(faq)}`;
          return (
            <section key={faq.question}>
              <h2>
                <button
                  type="button"
                  aria-expanded={opened === faq.question}
                  aria-controls={id}
                  onClick={() =>
                    setOpened(opened === faq.question ? null : faq.question)
                  }
                >
                  {faq.question}
                  <ChevronDown size={20} />
                </button>
              </h2>
              <AnimatePresence initial={false}>
                {opened === faq.question && (
                  <motion.div
                    id={id}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.24 }}
                  >
                    <p>{faq.answer}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </section>
          );
        })}
        {!filtered.length && (
          <p className="project-empty" role="status">
            Không có câu hỏi phù hợp. Thử một từ khóa ngắn hơn hoặc xem hướng
            dẫn sử dụng.
          </p>
        )}
      </div>
      <Link
        className="project-text-link"
        to={actor ? roleHome(actor.role) : "/dang-nhap"}
      >
        Mở ứng dụng <ArrowRight size={17} />
      </Link>
    </article>
  );
}
