import { ThemeToggle } from "../../components/ThemeToggle";
import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ArrowRight, Menu, X } from "lucide-react";
import { BrandLogo } from "../../components/BrandLogo";
import { useActor } from "../../app/identity";

const navLinks = [
  { to: "/gioi-thieu", label: "Giới thiệu" },
  { to: "/tinh-nang", label: "Tính năng" },
  { to: "/nghien-cuu", label: "Nghiên cứu" },
  { to: "/ve-chung-toi", label: "Về dự án" },
];

export function PortalHeader() {
  const actor = useActor();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const isHeroPage =
    location.pathname === "/" || location.pathname === "/gioi-thieu";
  const isTransparent = isHeroPage && !scrolled && !mobileOpen;

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [location.pathname]);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        document
          .querySelector<HTMLButtonElement>(".portal-mobile-toggle")
          ?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [mobileOpen]);

  const startRoute = actor ? "/" : "/dang-nhap";
  const startLabel = actor ? "Vào học tập" : "Đăng nhập";

  return (
    <header
      className={`portal-header ${
        isTransparent ? "is-transparent-hero" : "is-scrolled"
      }`}
    >
      <div className="portal-header-container">
        <BrandLogo
          to="/gioi-thieu"
          subtitle="Hỗ trợ ôn thi bác sĩ Y học dự phòng"
          theme={isTransparent ? "light" : "default"}
          size={38}
        />

        <nav
          className="portal-desktop-nav"
          aria-label="Điều hướng chính trang cổng thông tin"
        >
          {navLinks.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `portal-nav-link ${isActive ? "active" : ""}`
              }
            >
              {({ isActive }) => (
                <>
                  <span>{item.label}</span>
                  {isActive && (
                    <motion.span
                      className="portal-nav-indicator"
                      layoutId="portal-nav-indicator"
                      transition={{
                        type: "spring",
                        stiffness: 380,
                        damping: 34,
                      }}
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="portal-header-actions">
          <ThemeToggle />
          <Link to={startRoute} className="portal-cta-btn">
            <span>{startLabel}</span>
            <ArrowRight size={16} />
          </Link>

          <button
            type="button"
            className="portal-mobile-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Đóng menu" : "Mở menu"}
          >
            {mobileOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      <AnimatePresence initial={false}>
        {mobileOpen && (
          <motion.div
            className="portal-mobile-drawer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <nav aria-label="Điều hướng di động">
              {navLinks.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `portal-mobile-link ${isActive ? "active" : ""}`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              <div className="portal-mobile-divider" />
              <Link to="/lien-he" className="portal-mobile-link">
                Liên hệ chúng tôi
              </Link>
              <Link to={startRoute} className="portal-mobile-cta">
                {startLabel}
                <ArrowRight size={16} />
              </Link>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
