import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Pause,
  Play,
  ShieldCheck,
  Stethoscope,
  Timer,
  ChartNoAxesColumnIncreasing,
  BookOpen,
  Sparkles,
  Layers,
} from "lucide-react";
import { WaveDivider } from "../../components/WaveDivider";

export interface HeroSlide {
  id: string;
  image: string;
  alt: string;
  tag: string;
  titlePrimary: string;
  titleHighlight: string;
  subtext: string;
  primaryCta: { label: string; to: string };
  secondaryCta: { label: string; href: string };
  stats: Array<{
    icon: typeof Stethoscope;
    title: string;
    sub: string;
  }>;
}

const heroSlides: HeroSlide[] = [
  {
    id: "competency",
    image: "/images/medical/vietnam-medical-hero-banner.webp",
    alt: "Đội ngũ bác sĩ và chuyên gia y tế tại bệnh viện Việt Nam",
    tag: "DocPrep YHDP · CHUẨN NĂNG LỰC HÀNH NGHỀ BỘ Y TẾ",
    titlePrimary: "Học vững hôm nay.",
    titleHighlight: "Tự tin ngày hành nghề.",
    subtext:
      "Chuẩn hóa 54 vấn đề cốt lõi theo 8 chuẩn năng lực của Bộ Y tế, giải thích cặn kẽ và đối chiếu trực tiếp giáo trình chuẩn.",
    primaryCta: { label: "Trải nghiệm không gian ôn tập", to: "start" },
    secondaryCta: { label: "8 Chuẩn năng lực cốt lõi", href: "#chuan-nang-luc" },
    stats: [
      { icon: Stethoscope, title: "54 Vấn đề cốt lõi", sub: "8 Nhóm chuẩn năng lực BYT" },
      { icon: ShieldCheck, title: "Thẩm định 2 vòng", sub: "Hội đồng chuyên gia y khoa độc lập" },
      { icon: ClipboardCheck, title: "Đối chiếu y văn chuẩn", sub: "Mở tài liệu để đối chiếu" },
    ],
  },
  {
    id: "cbt-exam",
    image: "/images/medical/vietnam-cbt-exam-banner.webp",
    alt: "Bác sĩ và học viên thực hành phòng thi máy tính",
    tag: "MÔ PHỎNG KHẢO THÍ CHUẨN QUỐC GIA",
    titlePrimary: "Áp lực thi thực tế.",
    titleHighlight: "Rèn phản xạ phòng thi trắc nghiệm.",
    subtext:
      "Thi trắc nghiệm trên máy tính để làm quen với cách làm bài: đồng hồ đếm ngược, tự động lưu bài làm và phân tích năng lực chi tiết ngay khi nộp bài.",
    primaryCta: { label: "Thi thử trên máy tính", to: "/thi-thu" },
    secondaryCta: { label: "Các cấp độ đánh giá", href: "#chuan-nang-luc" },
    stats: [
      { icon: Timer, title: "Đếm ngược phòng thi", sub: "Mô phỏng kỳ thi máy tính thực tế" },
      { icon: ChartNoAxesColumnIncreasing, title: "Đánh giá đa cấp độ", sub: "Từ nhớ kiến thức đến xử trí thực địa" },
      { icon: ShieldCheck, title: "Tự động lưu bài làm", sub: "An tâm rà soát và nộp bài" },
    ],
  },
  {
    id: "clinical-cases",
    image: "/images/medical/vietnam-medical-training-banner.webp",
    alt: "Bác sĩ trẻ và học viên thảo luận ca bệnh và dịch tễ học thực địa",
    tag: "RÈN LUYỆN TƯ DUY CA BỆNH ĐA BƯỚC",
    titlePrimary: "Học qua từng ca bệnh.",
    titleHighlight: "Hiểu sâu cơ chế sinh bệnh.",
    subtext:
      "Thực hành suy luận tình huống lâm sàng thực địa, bóc tách nguyên nhân từ triệu chứng đến can thiệp y tế cơ sở và y tế công cộng.",
    primaryCta: { label: "Rèn luyện ca lâm sàng", to: "/tinh-huong" },
    secondaryCta: { label: "Cách tiếp cận ca bệnh", href: "#lo-trinh-tinh-nang" },
    stats: [
      { icon: Stethoscope, title: "Tình huống nhiều bước", sub: "Rèn luyện tư duy thực hành" },
      { icon: BookOpen, title: "Giải thích rõ đúng – sai", sub: "Phân tích vì sao chọn hoặc loại trừ" },
      { icon: Sparkles, title: "Ôn tập chống quên", sub: "Tự động nhắc lại điểm hay nhầm lẫn" },
    ],
  },
  {
    id: "epidemiology",
    image: "/images/medical/vietnam-lab-banner.webp",
    alt: "Chuyên gia y học dự phòng và dịch tễ học nghiên cứu phòng xét nghiệm",
    tag: "DỊCH TỄ HỌC & GIÁM SÁT SỨC KHỎE QUẦN THỂ",
    titlePrimary: "Giám sát dịch bệnh.",
    titleHighlight: "Chủ động bảo vệ cộng đồng.",
    subtext:
      "Hệ thống hóa phương pháp điều tra ổ dịch, phân tích hiện mắc và mới mắc, xây dựng can thiệp y tế cơ sở bám sát thực tiễn Việt Nam.",
    primaryCta: { label: "Ôn tập chuyên khoa", to: "/luyen-tap" },
    secondaryCta: { label: "Báo cáo nghiên cứu AIRC", href: "/nghien-cuu" },
    stats: [
      { icon: Layers, title: "Giám sát thực địa", sub: "Điều tra ổ dịch & nguồn lây" },
      { icon: ChartNoAxesColumnIncreasing, title: "Hiện mắc & Mới mắc", sub: "Chỉ số dịch tễ học cốt lõi" },
      { icon: ShieldCheck, title: "Y tế cơ sở", sub: "Bám sát thực tiễn Việt Nam" },
    ],
  },
  {
    id: "academic-sources",
    image: "/images/medical/vietnam-doctor-consult-banner.webp",
    alt: "Bác sĩ chuyên khoa hướng dẫn đối chiếu y văn và giáo trình chuẩn",
    tag: "ĐỌC LỜI GIẢI, KIỂM TRA TÀI LIỆU",
    titlePrimary: "Minh bạch nguồn gốc.",
    titleHighlight: "Đối chiếu tận gốc giáo trình.",
    subtext:
      "Mọi câu hỏi và kiến thức giải thích đều đối chiếu trực tiếp số trang giáo trình Đại học Y Hà Nội và quyết định chuyên môn của Bộ Y tế.",
    primaryCta: { label: "Thư viện giáo trình số", to: "/tai-lieu" },
    secondaryCta: { label: "Hội đồng thẩm định", href: "/ve-chung-toi" },
    stats: [
      { icon: BookOpen, title: "Giáo trình ĐHYHN", sub: "Trích dẫn số trang chính xác" },
      { icon: ShieldCheck, title: "Quyết định Bộ Y tế", sub: "Căn cứ chuyên môn pháp lý" },
      { icon: Sparkles, title: "Thẩm định độc lập", sub: "Nội dung chuẩn xác đã kiểm duyệt" },
    ],
  },
];

export function AntigravityHero({ start }: { start: string }) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isHovered, setIsHovered] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!isPlaying || isHovered || reduced) return;
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % heroSlides.length);
    }, 6000);
    return () => clearInterval(interval);
  }, [isPlaying, isHovered, reduced]);

  const slide = heroSlides[currentSlide];

  const handlePrev = () => {
    setCurrentSlide((prev) => (prev - 1 + heroSlides.length) % heroSlides.length);
  };

  const handleNext = () => {
    setCurrentSlide((prev) => (prev + 1) % heroSlides.length);
  };

  return (
    <section
      className="landing-hero-revamped antigravity-hero"
      aria-roledescription="carousel"
      aria-label="Giới thiệu nền tảng số ôn thi Bác sĩ Y học dự phòng"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocusCapture={() => setIsHovered(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          setIsHovered(false);
        }
      }}
    >
      {/* Background Images with Cinematic Crossfade Transition */}
      <div className="hero-img-container">
        <AnimatePresence initial={false}>
          <motion.img
            key={slide.id}
            className="hero-background-img"
            src={slide.image}
            alt={slide.alt}
            fetchPriority={currentSlide === 0 ? "high" : "auto"}
            initial={{ opacity: 0, scale: reduced ? 1 : 1.05 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
          />
        </AnimatePresence>

        {/* Cinematic Gradient Shade */}
        <div className="hero-gradient-overlay" />
        {/* Subtle Pulse Grid */}
        <div className="hero-pulse-grid" />
      </div>

      <div className="hero-content-wrapper">
        <div className="hero-inner-container">
          {/* Animated Slide Content (Tag, Headline, Shortened Subtext, CTAs, Stats) */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={slide.id}
              initial={{ opacity: 0, y: reduced ? 0 : 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduced ? 0 : -10 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="hero-slide-content-group"
            >
              {/* Badge */}
              <div className="hero-tag-badge">
                <span className="badge-pulse-dot" />
                <span>{slide.tag}</span>
              </div>

              {/* Title */}
              <h1 className="hero-main-title">
                <span className="hero-title-line">
                  {slide.titlePrimary.replace(/\s+(\S+)$/, "\u00a0$1")}
                </span>
                <span className="hero-title-line text-gradient-cyan">
                  {slide.titleHighlight.replace(/\s+(\S+)$/, "\u00a0$1")}
                </span>
              </h1>

              {/* Shortened Subtitle */}
              <p className="hero-subtext">{slide.subtext}</p>

              {/* CTAs */}
              <div className="hero-cta-group">
                <Link
                  className="btn-hero-primary"
                  to={slide.primaryCta.to === "start" ? start : slide.primaryCta.to}
                >
                  <span>{slide.primaryCta.label}</span>
                  <ArrowRight size={18} />
                </Link>

                <a className="btn-hero-outline" href={slide.secondaryCta.href}>
                  <span>{slide.secondaryCta.label}</span>
                  <ChevronRight size={16} />
                </a>
              </div>

              {/* Floating Stat Pills */}
              <div className="hero-stats-strip">
                {slide.stats.map((st, sIdx) => {
                  const Icon = st.icon;
                  return (
                    <div key={sIdx} className="stat-pill">
                      <Icon size={18} className="stat-pill-icon" />
                      <div>
                        <strong>{st.title}</strong>
                        <small>{st.sub}</small>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Interactive Carousel Nav & Progress Capsule */}
          <div className="hero-slider-controls">
            <button
              type="button"
              className="hero-slider-nav-btn prev"
              onClick={handlePrev}
              aria-label="Hình ảnh trước"
            >
              <ChevronLeft size={16} />
            </button>

            <div
              className="hero-slider-indicators"
              role="tablist"
              aria-label="Chuyển trang banner"
            >
              {heroSlides.map((s, idx) => {
                const isActive = idx === currentSlide;
                return (
                  <button
                    key={s.id}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    aria-label={`Hình ảnh ${idx + 1}: ${s.titlePrimary}`}
                    className={`hero-indicator-bar ${isActive ? "active" : ""}`}
                    onClick={() => setCurrentSlide(idx)}
                  >
                    {isActive && isPlaying && !reduced && (
                      <motion.span
                        key={`progress-${idx}`}
                        className="indicator-progress-fill"
                        initial={{ width: "0%" }}
                        animate={{ width: "100%" }}
                        transition={{ duration: 6, ease: "linear" }}
                      />
                    )}
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              className="hero-slider-nav-btn next"
              onClick={handleNext}
              aria-label="Hình ảnh tiếp theo"
            >
              <ChevronRight size={16} />
            </button>

            <button
              type="button"
              className="hero-slider-play-toggle"
              onClick={() => setIsPlaying((p) => !p)}
              aria-label={
                isPlaying ? "Tạm dừng tự động chuyển ảnh" : "Bật tự động chuyển ảnh"
              }
              title={isPlaying ? "Tạm dừng tự chuyển" : "Bật tự chuyển"}
            >
              {isPlaying ? <Pause size={13} /> : <Play size={13} />}
            </button>
          </div>
        </div>
      </div>

      {/* Organic Wave Divider Transition */}
      <WaveDivider fillColor="var(--hero-wave-fill, #ffffff)" showDots={false} />
    </section>
  );
}
