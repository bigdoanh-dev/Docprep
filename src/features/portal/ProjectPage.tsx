import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight, CheckCircle2, ListTree } from "lucide-react";
import { ScrollReveal } from "../../components/ScrollReveal";
export type ProjectSection = {
  id: string;
  title: string;
  paragraphs?: string[];
  items?: string[];
};
export type ProjectPageContent = {
  title: string;
  intro: string;
  photo?: { src: string; alt: string; caption: string };
  sections: ProjectSection[];
  action?: { to: string; label: string };
};
export function ProjectPage({ content }: { content: ProjectPageContent }) {
  return (
    <article className="project-editorial">
      <header className="editorial-heading project-container">
        <nav aria-label="Đường dẫn trang" className="editorial-breadcrumbs">
          <Link to="/gioi-thieu">Giới thiệu dự án</Link>
          <span aria-hidden="true">/</span>
          <span>{content.title}</span>
        </nav>
        <h1>{content.title}</h1>
        <p>{content.intro}</p>
      </header>
      {content.photo && (
        <figure className="editorial-photo project-container">
          <img
            src={content.photo.src}
            alt={content.photo.alt}
            width={1600}
            height={900}
            fetchPriority="high"
          />
          <figcaption>{content.photo.caption}</figcaption>
        </figure>
      )}
      <div className="editorial-layout project-container">
        <aside className="editorial-index">
          <div className="editorial-toc-card">
            <div className="editorial-toc-header">
              <ListTree size={16} className="toc-header-icon" />
              <span>MỤC LỤC BÁO CÁO</span>
            </div>
            <nav aria-label="Nội dung trang" className="editorial-toc-nav">
              {content.sections.map((section, idx) => (
                <a key={section.id} href={`#${section.id}`} className="editorial-toc-link">
                  <span className="toc-num">{String(idx + 1).padStart(2, "0")}</span>
                  <span className="toc-text">{section.title}</span>
                  <ChevronRight size={13} className="toc-arrow" />
                </a>
              ))}
            </nav>
          </div>
        </aside>
        <div className="editorial-body">
          {content.sections.map((section, idx) => (
            <ScrollReveal key={section.id}>
              <section id={section.id} className="editorial-section-card">
                <div className="editorial-section-header">
                  <span className="section-index-badge">MỤC {String(idx + 1).padStart(2, "0")}</span>
                  <h2>{section.title}</h2>
                </div>
                <div className="editorial-section-content">
                  {section.paragraphs?.map((text, pIdx) => (
                    <p key={pIdx} className="editorial-paragraph">{text}</p>
                  ))}
                  {section.items && (
                    <div className="editorial-item-grid">
                      {section.items.map((text, iIdx) => (
                        <div key={iIdx} className="editorial-item-card">
                          <CheckCircle2 size={16} className="item-check-icon" />
                          <span>{text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </ScrollReveal>
          ))}
          {content.action && (
            <Link className="project-button" to={content.action.to}>
              {content.action.label}
              <ArrowRight size={17} />
            </Link>
          )}
        </div>
      </div>
    </article>
  );
}
