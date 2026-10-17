import { ClipboardList, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";

/** Keep the two study entry points visible and consistent across home and learning. */
export function LearningActions() {
  return (
    <nav className="study-actions" aria-label="Luyện tập và thi thử">
      <Link to="/on-tap">
        <ListChecks size={20} strokeWidth={1.7} aria-hidden="true" />
        <span>Luyện câu hỏi</span>
      </Link>
      <Link to="/thi-thu">
        <ClipboardList size={20} strokeWidth={1.7} aria-hidden="true" />
        <span>Thi thử</span>
      </Link>
    </nav>
  );
}
