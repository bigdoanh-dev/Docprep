import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, MapPin, ArrowRight } from "lucide-react";
export function ContactPage() {
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("Góp ý về giao diện");
  const [message, setMessage] = useState("");
  const [prepared, setPrepared] = useState("");
  const [copied, setCopied] = useState(false);
  const prepare = (event: FormEvent) => {
    event.preventDefault();
    setPrepared(`Chủ đề: ${topic}\nNgười liên hệ: ${name}\n\n${message}`);
    setCopied(false);
  };
  return (
    <article className="project-contact project-container">
      <header className="editorial-heading">
        <nav aria-label="Đường dẫn trang">
          <Link to="/gioi-thieu">Giới thiệu dự án</Link>
          <span>/</span>
          <span>Liên hệ</span>
        </nav>
        <h1>
          Cùng góp ý để
          <br />
          nền tảng phù hợp hơn.
        </h1>
        <p>
          Phản hồi từ người học và giảng viên giúp xác định nội dung cần hoàn
          thiện. Bạn có thể chuẩn bị thông tin bên dưới để chuyển qua đầu mối
          của đơn vị tham gia dự án.
        </p>
      </header>
      <div className="project-contact-grid">
        <section>
          <h2>Đơn vị chủ trì theo thuyết minh</h2>
          <p>
            Viện Đào tạo Y học dự phòng và Y tế công cộng
            <br />
            Trường Đại học Y Hà Nội
          </p>
          <p className="project-contact-address">
            <MapPin size={20} />
            01 Tôn Thất Tùng, Hà Nội
          </p>
          <div className="project-contact-note">
            <h3>Phản hồi hữu ích gồm những gì?</h3>
            <p>
              Trang đang xem, thao tác đã thực hiện, kết quả bạn mong đợi và vấn
              đề gặp phải. Không đưa dữ liệu người bệnh hoặc thông tin tài khoản
              vào nội dung phản hồi.
            </p>
          </div>
          <Link className="project-text-link" to="/faq">
            Xem câu hỏi thường gặp <ArrowRight size={17} />
          </Link>
        </section>
        <section className="project-contact-form">
          <h2>Chuẩn bị nội dung liên hệ</h2>
          <p>
            Biểu mẫu này tạo nội dung để sao chép; chưa gửi thông tin đến bất kỳ
            đơn vị nào.
          </p>
          <form onSubmit={prepare}>
            <label>
              Họ tên hoặc tên hiển thị
              <input
                required
                value={name}
                maxLength={120}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
              />
            </label>
            <label>
              Chủ đề
              <select
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
              >
                <option>Góp ý về giao diện</option>
                <option>Góp ý học liệu</option>
                <option>Khả năng tiếp cận</option>
                <option>Trao đổi về dự án</option>
              </select>
            </label>
            <label>
              Nội dung
              <textarea
                rows={6}
                required
                value={message}
                maxLength={4000}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Mô tả ngắn gọn nội dung bạn muốn trao đổi…"
              />
            </label>
            <button className="project-button" type="submit">
              Tạo nội dung liên hệ <ArrowRight size={17} />
            </button>
          </form>
          {prepared && (
            <div className="project-prepared">
              <label>
                Nội dung đã chuẩn bị
                <textarea readOnly rows={6} value={prepared} />
              </label>
              <button
                type="button"
                className="project-text-link"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(prepared);
                    setCopied(true);
                  } catch {
                    setCopied(false);
                  }
                }}
              >
                {copied ? <Check size={17} /> : <Copy size={17} />}
                {copied ? "Đã sao chép" : "Sao chép nội dung"}
              </button>
              <p role="status">
                {copied
                  ? "Bạn có thể dán nội dung vào kênh liên hệ đang sử dụng."
                  : "Bạn cũng có thể chọn và sao chép trực tiếp phần nội dung trên."}
              </p>
            </div>
          )}
        </section>
      </div>
    </article>
  );
}
