import { useLocation } from "react-router-dom";
import { Coverage } from "./Coverage";
import { Library } from "./Library";
import { Queue } from "./Queue";
import { Reports } from "./Reports";
import { ReviewDetail } from "./ReviewDetail";
export default function ReviewWorkspace() {
  const loc = useLocation();
  if (loc.pathname.endsWith("/bao-loi")) return <Reports />;
  if (loc.pathname.endsWith("/hoc-lieu")) return <Library />;
  if (loc.pathname.endsWith("/bao-phu")) return <Coverage />;
  const id = loc.pathname.match(/\/cau\/([^/]+)$/)?.[1];
  return id ? <ReviewDetail id={decodeURIComponent(id)} /> : <Queue />;
}
