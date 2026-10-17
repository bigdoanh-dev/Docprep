import { useLocation } from "react-router-dom";
import { Dashboard } from "./Dashboard";
import { OperationsPage } from "./OperationsPage";
import { UserImport } from "./UserImport";
export default function ManagementWorkspace() {
  const loc = useLocation();
  if (loc.pathname.endsWith("/tai-khoan")) return <UserImport />;
  if (loc.pathname.startsWith("/quan-tri")) return <OperationsPage />;
  return <Dashboard />;
}
