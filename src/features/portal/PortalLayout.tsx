import { Link, Outlet } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { roleHome, useActor } from "../../app/identity";
export function PortalLayout() {
  const actor = useActor();
  return (
    <div className="mobile-legal">
      <header>
        <Link to={actor ? roleHome(actor.role) : "/dang-nhap"}>
          <ArrowLeft size={18} /> DocPrep
        </Link>
      </header>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
